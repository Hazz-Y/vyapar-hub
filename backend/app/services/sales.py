"""Sales summaries. All values are computed here, never by the LLM."""
from __future__ import annotations

import statistics
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Transaction


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def day_totals(session: Session, merchant_id: int, d: date) -> dict:
    start, end = _day_bounds(d)
    total, count = session.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0), func.count())
        .where(Transaction.merchant_id == merchant_id, Transaction.direction == "in",
               Transaction.ts >= start, Transaction.ts < end)
    ).one()
    return {"date": d.isoformat(), "total": int(total), "count": int(count)}


def daily_inflows(session: Session, merchant_id: int, start: date, end: date) -> dict[date, int]:
    """Inflow per day for start <= day < end (missing days = 0)."""
    s, _ = _day_bounds(start)
    e, _ = _day_bounds(end)
    rows = session.exec(
        select(func.date(Transaction.ts), func.sum(Transaction.amount))
        .where(Transaction.merchant_id == merchant_id, Transaction.direction == "in",
               Transaction.ts >= s, Transaction.ts < e)
        .group_by(func.date(Transaction.ts))
    ).all()
    out = {start + timedelta(days=i): 0 for i in range((end - start).days)}
    for d, total in rows:
        out[date.fromisoformat(str(d))] = int(total)
    return out


def usual_day(session: Session, merchant_id: int, d: date, weeks: int = 8) -> dict:
    """Median inflow of the same weekday over the `weeks` weeks before d."""
    days = [d - timedelta(days=7 * w) for w in range(1, weeks + 1)]
    inflows = daily_inflows(session, merchant_id, days[-1], d)
    values = [inflows[x] for x in days]
    return {"weekday": d.strftime("%A"), "weeks": weeks, "median": int(round(statistics.median(values))),
            "samples": values}


def pct_change(value: int, base: int) -> int | None:
    if base == 0:
        return None
    return int(round((value - base) * 100 / base))


def sales_summary(session: Session, merchant_id: int, today: date) -> dict:
    t = day_totals(session, merchant_id, today)
    y_date = today - timedelta(days=1)
    y = day_totals(session, merchant_id, y_date)
    usual_y = usual_day(session, merchant_id, y_date)
    usual_t = usual_day(session, merchant_id, today)
    return {
        "today": t,
        "yesterday": y,
        "usual_for_yesterday": usual_y["median"],
        "usual_for_today": usual_t["median"],
        "yesterday_vs_usual_pct": pct_change(y["total"], usual_y["median"]),
        "yesterday_weekday": usual_y["weekday"],
    }
