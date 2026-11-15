from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app import clock, scheduler
from app.deps import MerchantId, SessionDep, get_merchant
from app.models import PendingAction, SoundboxEvent, Udhaar
from app.services.customers import find_customer
from app.services.demo import reset_demo
from app.services.payments import record_inflow
from app.services.timetravel import fill_until, next_friday_10am

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset")
def reset() -> dict:
    return reset_demo()


class SimulatedPayment(BaseModel):
    amount: int = Field(gt=0, le=1_000_000)
    payer_name: str | None = None
    payer_hash: str | None = None


@router.post("/simulate-payment")
def simulate_payment(body: SimulatedPayment, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    get_merchant(session, merchant_id)
    customer = find_customer(session, merchant_id, body.payer_name) if body.payer_name else None
    if body.payer_name and customer is None and not body.payer_hash:
        raise HTTPException(404, f"No customer matches '{body.payer_name}'")
    return record_inflow(session, merchant_id, body.amount, clock.now(), customer=customer,
                         payer_hash=body.payer_hash, payer_name=body.payer_name)


@router.post("/jump-to-friday")
def jump_to_friday(session: SessionDep) -> dict:
    """Skip ahead to Friday 10:00 (reminder time), filling the skipped days, then run the scheduler."""
    start = clock.now()
    target = next_friday_10am(start)
    filled = fill_until(session, start, target)
    session.commit()
    clock.set_now(target)
    return {"from": start.isoformat(), "to": target.isoformat(), "filled": filled, "tick": scheduler.tick(target)}


@router.get("/state")
def state(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    get_merchant(session, merchant_id)
    now, start = clock.now(), clock.demo_start()

    def count(model, *where) -> int:
        return session.exec(select(func.count()).select_from(model).where(model.merchant_id == merchant_id, *where)).one()

    last_event = session.exec(select(func.max(SoundboxEvent.id)).where(SoundboxEvent.merchant_id == merchant_id)).one()
    return {
        "now": now.isoformat(), "demo_date": start.isoformat(), "day": (now.date() - start).days,
        "next_jump": next_friday_10am(now).isoformat(),
        "pending_actions": count(PendingAction, PendingAction.status == "pending"),
        "open_udhaar": count(Udhaar, Udhaar.status != "settled"),
        "last_soundbox_event_id": last_event or 0,
    }
