"""GST-ready purchase register (CSV) from paid supplier invoices.

Payable amounts are GST-inclusive invoice totals. Taxable value = total * 100 / (100 + rate).
Intra-state (supplier GSTIN state code == shop's state) splits tax into CGST + SGST; otherwise IGST.
Suppliers without a GSTIN are unregistered: no input tax credit (ITC).
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.models import Merchant, Payable, Supplier, Transaction

STATE_CODES = {"Kanpur": "09", "Lucknow": "09", "Chennai": "33", "Mumbai": "27", "Delhi": "07"}
COLUMNS = ["invoice_date", "invoice_no", "supplier_name", "supplier_gstin", "category", "taxable_value",
           "gst_rate_pct", "cgst", "sgst", "igst", "invoice_total", "payment_date", "payment_ref", "itc_eligible"]
PAISE = Decimal("0.01")


def split_tax(total: int | Decimal, rate_pct: int, intra_state: bool) -> dict[str, Decimal]:
    total = Decimal(total)
    taxable = (total * 100 / (100 + rate_pct)).quantize(PAISE, ROUND_HALF_UP)
    tax = total - taxable
    if intra_state:
        cgst = (tax / 2).quantize(PAISE, ROUND_HALF_UP)
        return {"taxable_value": taxable, "cgst": cgst, "sgst": tax - cgst, "igst": Decimal("0.00")}
    return {"taxable_value": taxable, "cgst": Decimal("0.00"), "sgst": Decimal("0.00"), "igst": tax}


def month_range(month: str | None, today: date) -> tuple[date, date]:
    """'YYYY-MM' -> [first day, first day of next month). Default: the last full month."""
    if month:
        y, m = map(int, month.split("-"))
        start = date(y, m, 1)
    else:
        first_this = today.replace(day=1)
        start = (first_this - timedelta(days=1)).replace(day=1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, end


def gst_rows(session: Session, merchant: Merchant, start: date, end: date) -> list[dict]:
    shop_state = STATE_CODES.get(merchant.city)
    rows = session.exec(
        select(Payable, Supplier, Transaction).join(Supplier, Payable.supplier_id == Supplier.id)
        .join(Transaction, Payable.paid_txn_id == Transaction.id, isouter=True)
        .where(Payable.merchant_id == merchant.id, Payable.status == "paid",
               Payable.due_date >= start, Payable.due_date < end)
        .order_by(Payable.due_date, Payable.id)).all()
    out = []
    for p, s, t in rows:
        intra = not s.gstin or shop_state is None or s.gstin[:2] == shop_state
        tax = split_tax(p.amount, p.gst_rate, intra)
        out.append({
            "invoice_date": p.due_date.isoformat(), "invoice_no": p.invoice_no or "", "supplier_name": s.name,
            "supplier_gstin": s.gstin or "UNREGISTERED", "category": s.category,
            "taxable_value": str(tax["taxable_value"]), "gst_rate_pct": p.gst_rate, "cgst": str(tax["cgst"]),
            "sgst": str(tax["sgst"]), "igst": str(tax["igst"]), "invoice_total": f"{Decimal(p.amount):.2f}",
            "payment_date": (t.ts.date().isoformat() if t else ""), "payment_ref": f"TXN{t.id}" if t else "",
            "itc_eligible": "yes" if (s.gstin and p.gst_rate > 0) else "no"})
    return out


def gst_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
