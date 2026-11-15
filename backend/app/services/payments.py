"""Incoming QR payments (simulated in the demo) and Soundbox announcement text."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from app.models import Customer, Transaction
from app.services.customers import display_name
from app.services.hardware import send_raw
from app.services.messaging import announce as announce_event
from app.services.udhaar import settle_on_inflow


def soundbox_payment_text(amount: int) -> str:
    return f"Paytm par {amount} rupaye prapt hue"


def record_inflow(session: Session, merchant_id: int, amount: int, now: datetime,
                  customer: Customer | None = None, payer_hash: str | None = None,
                  payer_name: str | None = None) -> dict:
    if amount <= 0:
        raise ValueError("amount must be positive")
    txn = Transaction(merchant_id=merchant_id, ts=now, amount=amount, direction="in",
                      payer_hash=customer.payer_hash if customer else payer_hash,
                      counterparty=customer.name if customer else payer_name, source="qr",
                      note="Simulated QR payment (demo)")
    session.add(txn)
    session.commit()
    session.refresh(txn)
    settled = settle_on_inflow(session, txn)
    announce = soundbox_payment_text(amount)
    result = {"transaction_id": txn.id, "amount": amount, "ts": txn.ts.isoformat(),
              "soundbox_text": announce, "settled_udhaar": None}
    if settled:
        c = session.get(Customer, settled.customer_id)
        name = display_name(c.name)
        result["settled_udhaar"] = {"id": settled.id, "customer": name, "amount": settled.amount}
        result["soundbox_text"] = f"{announce}. {name} ka {settled.amount} rupaye ka udhaar band ho gaya"
    result["soundbox_event_id"] = announce_event(session, merchant_id, "payment", result["soundbox_text"], now).id
    payer = customer.name if customer else (payer_name or "Paytm QR")
    sub = f"{result['settled_udhaar']['customer']} Udhaar Closed" if settled else f"UPI TXN: {txn.id}"
    send_raw("PAYMENT SUCCESS", f"Rs {amount:.2f}", payer, sub)
    return result
