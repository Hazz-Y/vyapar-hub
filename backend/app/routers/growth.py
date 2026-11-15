from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import clock
from app.agent.tools import DraftWinbackIn, draft_winback
from app.deps import MerchantId, SessionDep, get_merchant
from app.routers.agent import make_context
from app.services.insights import growth_insights, lapsed_regulars
from app.services.actions import action_out

router = APIRouter(prefix="/growth", tags=["growth"])


@router.get("/insights")
def insights(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    get_merchant(session, merchant_id)
    return growth_insights(session, merchant_id, clock.today())


@router.get("/lapsed")
def lapsed(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    rows = lapsed_regulars(session, merchant_id, clock.today())
    return {"count": len(rows), "opted_in_count": sum(r["opted_in"] for r in rows), "customers": rows}


class WinbackDraft(BaseModel):
    discount_pct: int = Field(10, ge=1, le=50)
    customer_ids: list[int] | None = None


@router.post("/winback/draft")
def winback_draft(body: WinbackDraft, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    """One-tap win-back: same tool the agent uses; creates a PendingAction (or sends in auto mode)."""
    ctx = make_context(session, merchant_id)
    result = draft_winback(ctx, DraftWinbackIn(**body.model_dump()))
    return {**result, "pending_actions": [action_out(a) for a in ctx.actions]}
