from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import clock
from app.deps import MerchantId, SessionDep, get_merchant
from app.models import Customer
from app.seed import hash_payer
from app.services.customers import find_customer
from app.services.udhaar import create_udhaar, list_udhaar, udhaar_row, udhaar_totals

router = APIRouter(tags=["udhaar"])


@router.get("/udhaar")
def udhaar_list(session: SessionDep, merchant_id: MerchantId = 1,
                status: Literal["open", "reminded", "settled"] | None = None) -> dict:
    today = clock.today()
    return {"entries": list_udhaar(session, merchant_id, today, status),
            "totals": udhaar_totals(session, merchant_id, today)}


class UdhaarCreate(BaseModel):
    customer_name: str = Field(min_length=1)
    amount: int = Field(gt=0, le=1_000_000)
    due_date: date
    phone: str | None = Field(default=None, description="Typed in by the merchant (consent)")
    note: str = ""


@router.post("/udhaar", status_code=201)
def udhaar_create(body: UdhaarCreate, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    """Direct entry typed by the merchant in the UI. Voice entries go through the agent's read-back."""
    get_merchant(session, merchant_id)
    c = find_customer(session, merchant_id, body.customer_name)
    if c is None:
        if not body.phone:
            raise HTTPException(422, "New customer: please type their phone number")
        c = Customer(merchant_id=merchant_id, name=body.customer_name.strip(), phone=body.phone,
                     payer_hash=hash_payer(f"manual:{merchant_id}:{body.customer_name}:{body.phone}"),
                     opted_in=False)
        session.add(c)
        session.commit()
        session.refresh(c)
    elif body.phone:
        c.phone = body.phone
        session.add(c)
        session.commit()
    u, created = create_udhaar(session, merchant_id, c.id, body.amount, body.due_date, clock.now(), body.note)
    return {"created": created, "entry": udhaar_row(u, c, clock.today())}


@router.post("/udhaar/{udhaar_id}/remind")
def udhaar_remind(udhaar_id: int, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    """Draft a reminder (sent at once if the udhaar agent is in auto mode)."""
    from app.agent.tools import DraftReminderIn, draft_udhaar_reminder
    from app.routers.agent import make_context
    from app.services.actions import action_out

    ctx = make_context(session, merchant_id)
    r = draft_udhaar_reminder(ctx, DraftReminderIn(udhaar_id=udhaar_id))
    if "error" in r:
        raise HTTPException(422, r["speak"])
    return {**r, "pending_actions": [action_out(a) for a in ctx.actions]}
