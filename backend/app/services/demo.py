"""Demo state: reset (re-seed + clock) and the simulated clock helpers."""
from datetime import date, datetime

from app import clock
from app.config import get_settings
from app.db import get_engine
from app.seed import DEMO_START_TIME, seed_all


def demo_date() -> date:
    s = get_settings()
    if s.demo_now:
        return datetime.fromisoformat(s.demo_now).date()
    if s.demo_date:
        return date.fromisoformat(s.demo_date)
    return clock.real_now().date()


def reset_demo() -> dict:
    s = get_settings()
    d = demo_date()
    counts = seed_all(get_engine(), d)
    start = datetime.fromisoformat(s.demo_now) if s.demo_now else datetime.combine(d, DEMO_START_TIME)
    clock.set_now(start)
    clock.set_demo_start(d)
    return {"demo_date": d.isoformat(), "clock": start.isoformat(), "rows": counts}


def warm_models() -> None:
    """Train/cache each merchant's forecast so the first radar or voice turn is fast."""
    from sqlmodel import Session, select

    from app.models import Merchant
    from app.services.forecast import get_model

    with Session(get_engine()) as s:
        for m in s.exec(select(Merchant)).all():
            get_model(s, m.id, clock.today())


def warm_connections() -> None:
    """Open the LLM HTTPS connection with a free models-list call (no tokens), so turn 1 isn't cold."""
    from app.agent.runner import client_from_settings

    client = client_from_settings()
    if client is None:
        return
    try:
        client.client.models.list()
    except Exception:
        pass  # warm-up is best effort


def warm_up() -> None:
    warm_models()
    warm_connections()
