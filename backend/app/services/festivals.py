"""Festival calendar from data/festivals.csv."""
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

from app.config import BACKEND_DIR

FESTIVAL_CSV = BACKEND_DIR / "data" / "festivals.csv"


@dataclass(frozen=True)
class Festival:
    name: str
    day: date
    duration_days: int
    lead_days: int

    @property
    def end(self) -> date:
        return self.day + timedelta(days=self.duration_days - 1)

    @property
    def window_start(self) -> date:
        return self.day - timedelta(days=self.lead_days)


@lru_cache
def load_festivals() -> tuple[Festival, ...]:
    with FESTIVAL_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fests = [
        Festival(r["festival"], date.fromisoformat(r["date"]), int(r["duration_days"]), int(r["lead_days"]))
        for r in rows
    ]
    return tuple(sorted(fests, key=lambda x: x.day))


def festival_on(d: date) -> Festival | None:
    """Festival whose window (lead days + duration) contains d."""
    for f in load_festivals():
        if f.window_start <= d <= f.end:
            return f
    return None


def days_to_next_festival(d: date, cap: int = 60) -> int:
    for f in load_festivals():
        if f.end >= d:
            return min(max((f.day - d).days, 0), cap)
    return cap


def same_festival_last_year(name: str, ref: date) -> tuple[Festival | None, Festival | None]:
    """Most recent occurrence of `name` on or before ref, and the one a year before it."""
    past = [f for f in load_festivals() if f.name == name and f.day <= ref]
    if not past:
        return None, None
    latest = past[-1]
    prev = past[-2] if len(past) > 1 else None
    return latest, prev


def most_recent_festival(ref: date) -> Festival | None:
    past = [f for f in load_festivals() if f.end < ref]
    return past[-1] if past else None
