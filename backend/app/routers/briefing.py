from fastapi import APIRouter

from app import clock
from app.deps import MerchantId, SessionDep, get_merchant
from app.services.briefing import build_briefing
from app.services.messaging import soundbox_events

router = APIRouter(tags=["briefing"])


@router.get("/briefing/today")
def briefing_today(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    m = get_merchant(session, merchant_id)
    return build_briefing(session, m, clock.today(), clock.now(), clock.demo_start())


@router.get("/soundbox/events")
def events(session: SessionDep, merchant_id: MerchantId = 1, after_id: int = 0) -> list[dict]:
    """Polled by the Soundbox simulator. Each event's text is read out with /voice/speak."""
    return [{"id": e.id, "kind": e.kind, "text": e.text, "created_at": e.created_at.isoformat()}
            for e in soundbox_events(session, merchant_id, after_id)]
