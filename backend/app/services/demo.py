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
