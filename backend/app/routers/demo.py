from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import clock
from app.deps import MerchantId, SessionDep, get_merchant
from app.services.customers import find_customer
from app.services.demo import reset_demo
from app.services.payments import record_inflow

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
