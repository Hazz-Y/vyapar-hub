"""PendingAction creation and serialisation. Drafting never executes anything."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from app.models import PendingAction

MONEY_KINDS = {"pay_supplier", "reschedule_payable"}  # always need approval
MESSAGE_KINDS = {"send_reminder", "send_winback"}  # may skip approval in auto mode
KINDS = MONEY_KINDS | MESSAGE_KINDS | {"log_udhaar"}


def create_pending(session: Session, merchant_id: int, agent: str, kind: str, payload: dict,
                   readback_text: str, now: datetime) -> PendingAction:
    if kind not in KINDS:
        raise ValueError(f"unknown action kind {kind}")
    pa = PendingAction(merchant_id=merchant_id, agent=agent, kind=kind, payload=payload,
                       readback_text=readback_text, status="pending", created_at=now)
    session.add(pa)
    session.commit()
    session.refresh(pa)
    return pa


def action_out(pa: PendingAction) -> dict:
    return {"id": pa.id, "agent": pa.agent, "kind": pa.kind, "payload": pa.payload,
            "readback_text": pa.readback_text, "status": pa.status, "created_at": pa.created_at.isoformat(),
            "executed_at": pa.executed_at.isoformat() if pa.executed_at else None,
            "result_text": pa.result_text, "amount": pa.payload.get("amount"),
            "recipient": pa.payload.get("recipient")}
