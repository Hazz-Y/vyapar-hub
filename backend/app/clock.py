"""Simulated demo clock (IST, naive datetimes).

The clock is stored as a pair (demo_base, real_base) in AppState:
    now = demo_base + (real_now - real_base)
so time keeps flowing during the pitch, and "jump to Friday" just moves demo_base.
"""
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session

from app.db import get_engine
from app.models import AppState

IST = timezone(timedelta(hours=5, minutes=30))
_DEMO_BASE = "clock_demo_base"
_REAL_BASE = "clock_real_base"


def real_now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)


def set_now(target: datetime) -> None:
    with Session(get_engine()) as s:
        for key, val in ((_DEMO_BASE, target), (_REAL_BASE, real_now())):
            row = s.get(AppState, key)
            if row is None:
                s.add(AppState(key=key, value=val.isoformat()))
            else:
                row.value = val.isoformat()
                s.add(row)
        s.commit()


def now() -> datetime:
    with Session(get_engine()) as s:
        demo = s.get(AppState, _DEMO_BASE)
        real = s.get(AppState, _REAL_BASE)
    if demo is None or real is None:
        return real_now()
    elapsed = real_now() - datetime.fromisoformat(real.value)
    return datetime.fromisoformat(demo.value) + max(elapsed, timedelta(0))


def today() -> date:
    return now().date()


def set_demo_start(d: date) -> None:
    with Session(get_engine()) as s:
        row = s.get(AppState, "demo_date") or AppState(key="demo_date", value="")
        row.value = d.isoformat()
        s.add(row)
        s.commit()


def demo_start() -> date:
    """The seeded demo date (history ends the day before; balances start that morning)."""
    with Session(get_engine()) as s:
        row = s.get(AppState, "demo_date")
    return date.fromisoformat(row.value) if row else today()
