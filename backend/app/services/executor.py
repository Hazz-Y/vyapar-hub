"""Executes approved PendingActions. This is the ONLY place that changes money state or sends messages.

* Approval needs the demo PIN (DEMO_PIN, a mock; never a real UPI PIN). 5 wrong tries reject the action.
* Payments and reschedules always need the PIN. Reminders and win-back offers may be auto-approved
  when the merchant set that agent to "auto".
* No real money moves: a "payment" writes a demo Transaction row.
"""
from __future__ import annotations

import hmac
from datetime import date, datetime

from sqlmodel import Session, select

from app.config import get_settings
from app.models import Customer, Payable, PendingAction, Settings, Supplier, Transaction, Udhaar
from app.seed import hash_payer
from app.services.actions import MESSAGE_KINDS, MONEY_KINDS
from app.services.customers import display_name
from app.services.fmt import fmt_date, rupees
from app.services.messaging import announce, send_message
from app.services.udhaar import OPEN_STATUSES, create_udhaar

MAX_PIN_FAILURES = 5
AUTONOMY_FIELD = {"udhaar": "autonomy_udhaar", "growth": "autonomy_growth"}


class ApprovalError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def pin_ok(pin: str) -> bool:
    return hmac.compare_digest(str(pin).encode(), get_settings().demo_pin.encode())


def autonomy_allows(session: Session, pa: PendingAction) -> bool:
    """Auto mode applies only to customer messages; money actions always need the PIN."""
    if pa.kind in MONEY_KINDS or pa.kind not in MESSAGE_KINDS:
        return False
    row = session.get(Settings, pa.merchant_id)
    field = AUTONOMY_FIELD.get(pa.agent)
    return bool(row and field and getattr(row, field) == "auto")


def approve(session: Session, action_id: int, pin: str, now: datetime) -> dict:
    pa = _pending(session, action_id)
    if not pin_ok(pin):
        pa.pin_failures += 1
        if pa.pin_failures >= MAX_PIN_FAILURES:
            pa.status, pa.result_text = "rejected", "Too many wrong PIN attempts."
        session.add(pa)
        session.commit()
        left = max(MAX_PIN_FAILURES - pa.pin_failures, 0)
        raise ApprovalError(403, f"Galat PIN. {left} koshish baaki." if left else "Galat PIN. Action radd ho gaya.")
    return execute(session, pa, now, approved_by="pin")


def auto_approve(session: Session, pa: PendingAction, now: datetime) -> dict | None:
    if not autonomy_allows(session, pa):
        return None
    return execute(session, pa, now, approved_by="auto")


def reject(session: Session, action_id: int, now: datetime) -> PendingAction:
    pa = _pending(session, action_id)
    pa.status, pa.executed_at, pa.result_text = "rejected", now, "Rejected by merchant. Nothing was done."
    session.add(pa)
    session.commit()
    session.refresh(pa)
    return pa


def _pending(session: Session, action_id: int) -> PendingAction:
    pa = session.get(PendingAction, action_id)
    if pa is None:
        raise ApprovalError(404, "Action not found")
    if pa.status != "pending":
        raise ApprovalError(409, f"Action is already {pa.status}")
    return pa


def execute(session: Session, pa: PendingAction, now: datetime, approved_by: str) -> dict:
    if pa.kind in MONEY_KINDS and approved_by != "pin":
        raise ApprovalError(403, "Payments and reschedules always need the PIN")
    handler = HANDLERS[pa.kind]
    try:
        confirmation, soundbox_text = handler(session, pa, now)
    except Exception:
        session.rollback()  # all-or-nothing: no half-applied action
        raise
    pa.status, pa.executed_at, pa.result_text, pa.approved_by = "executed", now, confirmation, approved_by
    session.add(pa)
    session.commit()
    session.refresh(pa)
    event_id = announce(session, pa.merchant_id, "action", soundbox_text, now).id if soundbox_text else None
    return {"action_id": pa.id, "kind": pa.kind, "status": pa.status, "approved_by": approved_by,
            "confirmation_text": confirmation, "soundbox_text": soundbox_text, "soundbox_event_id": event_id}


# ---------------------------------------------------------------- handlers: return (confirmation, soundbox)


def _pay_supplier(session: Session, pa: PendingAction, now: datetime) -> tuple[str, str]:
    p = pa.payload
    sup = session.get(Supplier, p["supplier_id"])
    if sup is None or sup.merchant_id != pa.merchant_id:
        raise ApprovalError(409, "Supplier no longer exists")
    txn = Transaction(merchant_id=pa.merchant_id, ts=now, amount=int(p["amount"]), direction="out",
                      counterparty=sup.name, note=f"Demo payment to {sup.name} (approved action {pa.id})",
                      source="supplier_payment")
    session.add(txn)
    session.flush()
    if p.get("payable_id"):
        payable = session.get(Payable, p["payable_id"])
        if payable and payable.status in ("scheduled", "rescheduled"):
            payable.status, payable.paid_txn_id = "paid", txn.id
            session.add(payable)
    amt = rupees(p["amount"])
    return (f"{amt} {sup.name} ko bhej diye (demo, koi asli paisa nahi gaya).",
            f"{sup.name} ko {int(p['amount'])} rupaye bheje gaye")


def _reschedule(session: Session, pa: PendingAction, now: datetime) -> tuple[str, str]:
    p = pa.payload
    payable = session.get(Payable, p["payable_id"])
    if payable is None or payable.status not in ("scheduled", "rescheduled"):
        raise ApprovalError(409, "This payment is no longer scheduled")
    new = date.fromisoformat(p["new_due_date"])
    if payable.original_due_date is None:
        payable.original_due_date = payable.due_date
    payable.due_date, payable.status = new, "rescheduled"
    session.add(payable)
    return (f"{p['supplier']} ka {rupees(p['amount'])} payment ab {fmt_date(new)} ko hoga.",
            f"{p['supplier']} ka payment {new.day} {new.strftime('%B')} ko shift ho gaya")


def _log_udhaar(session: Session, pa: PendingAction, now: datetime) -> tuple[str, str | None]:
    p = pa.payload
    if p.get("customer_id"):
        c = session.get(Customer, p["customer_id"])
        if p.get("phone"):
            c.phone = p["phone"]  # typed / said by the merchant
            session.add(c)
    else:
        c = Customer(merchant_id=pa.merchant_id, name=p["customer_name"], phone=p.get("phone") or "",
                     payer_hash=hash_payer(f"manual:{pa.merchant_id}:{p['customer_name']}:{p.get('phone')}"),
                     opted_in=False)
        session.add(c)
        session.flush()
    due = date.fromisoformat(p["due_date"])
    u, created = create_udhaar(session, pa.merchant_id, c.id, int(p["amount"]), due, now, p.get("note", ""))
    p_name = display_name(c.name)
    text = (f"{p_name} ka {rupees(u.amount)} udhaar likh liya. {fmt_date(due)} ko 10 baje yaad dila denge."
            if created else
            f"{p_name} ka {rupees(u.amount)} udhaar pehle se likha hai. {fmt_date(due)} ko 10 baje yaad dila denge.")
    return text, None


def _send_reminder(session: Session, pa: PendingAction, now: datetime) -> tuple[str, str | None]:
    p = pa.payload
    u = session.get(Udhaar, p["udhaar_id"])
    if u is None or u.status not in OPEN_STATUSES:
        raise ApprovalError(409, "This udhaar is already settled")
    c = session.get(Customer, u.customer_id)
    if not c.phone:
        raise ApprovalError(409, "No phone number for this customer")
    log = send_message(session, pa.merchant_id, c.phone, p["body"], "udhaar_reminder", now, commit=False)
    u.status, u.reminded_at = "reminded", now
    session.add(u)
    session.flush()
    pa.payload = {**p, "message_log_id": log.id}
    return f"{display_name(c.name)} ko reminder bhej diya (preview).", None


def _send_winback(session: Session, pa: PendingAction, now: datetime) -> tuple[str, str | None]:
    sent, skipped = 0, 0
    for m in pa.payload["messages"]:
        c = session.get(Customer, m["customer_id"])
        if c is None or not c.opted_in or not c.phone:  # consent re-checked at send time
            skipped += 1
            continue
        send_message(session, pa.merchant_id, c.phone, m["body"], "winback", now, commit=False)
        sent += 1
    text = f"{sent} grahakon ko offer bhej diya (preview)."
    if skipped:
        text += f" {skipped} ko nahi bheja (consent nahi)."
    return text, None


HANDLERS = {"pay_supplier": _pay_supplier, "reschedule_payable": _reschedule, "log_udhaar": _log_udhaar,
            "send_reminder": _send_reminder, "send_winback": _send_winback}


def pending_actions(session: Session, merchant_id: int, status: str | None = "pending") -> list[PendingAction]:
    stmt = select(PendingAction).where(PendingAction.merchant_id == merchant_id)
    if status:
        stmt = stmt.where(PendingAction.status == status)
    return list(session.exec(stmt.order_by(PendingAction.id.desc()).limit(50)).all())
