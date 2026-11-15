"""Udhaar (customer credit) book: log, list, and auto-close on matching payment."""
from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Session, select

from app.models import Customer, Transaction, Udhaar
from app.services.customers import display_name, normalise_name

OPEN_STATUSES = ("open", "reminded")


def udhaar_row(u: Udhaar, c: Customer, today: date) -> dict:
    return {
        "id": u.id, "customer_id": c.id, "customer_name": c.name, "display_name": display_name(c.name),
        "phone": c.phone, "amount": u.amount, "due_date": u.due_date.isoformat(), "status": u.status,
        "created_at": u.created_at.isoformat(), "days_to_due": (u.due_date - today).days,
        "overdue": u.status in OPEN_STATUSES and u.due_date < today,
        "settled_txn_id": u.settled_txn_id, "note": u.note,
        "reminded_at": u.reminded_at.isoformat() if u.reminded_at else None,
    }


def list_udhaar(session: Session, merchant_id: int, today: date, status: str | None = None) -> list[dict]:
    stmt = select(Udhaar, Customer).join(Customer).where(Udhaar.merchant_id == merchant_id)
    if status == "open":
        stmt = stmt.where(Udhaar.status.in_(OPEN_STATUSES))
    elif status:
        stmt = stmt.where(Udhaar.status == status)
    rows = session.exec(stmt.order_by(Udhaar.due_date, Udhaar.id)).all()
    return [udhaar_row(u, c, today) for u, c in rows]


def udhaar_totals(session: Session, merchant_id: int, today: date) -> dict:
    rows = list_udhaar(session, merchant_id, today, "open")
    due_now = [r for r in rows if r["days_to_due"] <= 0]
    return {
        "open_count": len(rows), "open_total": sum(r["amount"] for r in rows),
        "due_today_or_overdue_count": len(due_now), "due_today_or_overdue_total": sum(r["amount"] for r in due_now),
        "due_today_or_overdue": [{"name": r["display_name"], "amount": r["amount"]} for r in due_now],
    }


def create_udhaar(session: Session, merchant_id: int, customer_id: int, amount: int, due_date: date,
                  now: datetime, note: str = "") -> tuple[Udhaar, bool]:
    """Log an entry. An identical open entry (same customer, amount, due date) is reused, not duplicated."""
    existing = session.exec(select(Udhaar).where(
        Udhaar.merchant_id == merchant_id, Udhaar.customer_id == customer_id, Udhaar.amount == amount,
        Udhaar.due_date == due_date, Udhaar.status.in_(OPEN_STATUSES))).first()
    if existing:
        return existing, False
    u = Udhaar(merchant_id=merchant_id, customer_id=customer_id, amount=amount, created_at=now,
               due_date=due_date, status="open", note=note)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u, True


def match_open_udhaar(session: Session, txn: Transaction) -> Udhaar | None:
    """Payer hash first (exact amount preferred, else oldest entry the payment covers),
    then payer name plus exact amount."""
    open_rows = session.exec(select(Udhaar, Customer).join(Customer).where(
        Udhaar.merchant_id == txn.merchant_id, Udhaar.status.in_(OPEN_STATUSES))
        .order_by(Udhaar.due_date, Udhaar.id)).all()
    if txn.payer_hash:
        by_hash = [u for u, c in open_rows if c.payer_hash == txn.payer_hash]
        exact = [u for u in by_hash if u.amount == txn.amount]
        if exact:
            return exact[0]
        covered = [u for u in by_hash if u.amount <= txn.amount]
        if covered:
            return covered[0]
    if txn.counterparty:
        name = normalise_name(txn.counterparty)
        for u, c in open_rows:
            cname = c.name.lower()
            if u.amount == txn.amount and name and (cname == name or cname.split()[0] == name.split()[0]):
                return u
    return None


def settle_on_inflow(session: Session, txn: Transaction) -> Udhaar | None:
    u = match_open_udhaar(session, txn)
    if u is None:
        return None
    u.status = "settled"
    u.settled_txn_id = txn.id
    session.add(u)
    session.commit()
    session.refresh(u)
    return u
