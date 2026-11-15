from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import clock
from app.deps import MerchantId, SessionDep
from app.models import PendingAction
from app.services import speech
from app.services.actions import action_out
from app.services.executor import ApprovalError, approve, pending_actions, reject

router = APIRouter(prefix="/actions", tags=["actions"])


class ApproveRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=6, description="Demo PIN (mock, never a real UPI PIN)")


@router.get("")
def list_actions(session: SessionDep, merchant_id: MerchantId = 1,
                 status: Literal["pending", "executed", "rejected"] | None = "pending") -> list[dict]:
    return [action_out(a) for a in pending_actions(session, merchant_id, status)]


@router.get("/{action_id}")
def get_action(action_id: int, session: SessionDep) -> dict:
    pa = session.get(PendingAction, action_id)
    if pa is None:
        raise HTTPException(404, "Action not found")
    return action_out(pa)


@router.post("/{action_id}/approve")
def approve_action(action_id: int, body: ApproveRequest, session: SessionDep, speak: bool = True) -> dict:
    try:
        result = approve(session, action_id, body.pin, clock.now())
    except ApprovalError as e:
        raise HTTPException(e.status, e.message)
    text = result["soundbox_text"] or result["confirmation_text"]
    result["audio"] = speech.speak(text) if speak else None
    result["action"] = action_out(session.get(PendingAction, action_id))
    return result


@router.post("/{action_id}/reject")
def reject_action(action_id: int, session: SessionDep) -> dict:
    try:
        pa = reject(session, action_id, clock.now())
    except ApprovalError as e:
        raise HTTPException(e.status, e.message)
    return {"action": action_out(pa), "confirmation_text": "Theek hai, kuch nahi kiya."}
