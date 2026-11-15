"""Growth insights computed from transactions. Every number here is returned ready to show."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Customer, Transaction

VISIT_SOURCES = ("qr", "udhaar_settlement")


def lapsed_regulars(session: Session, merchant_id: int, today: date, min_visits: int = 4,
                    lookback_days: int = 90, quiet_days: int = 21) -> list[dict]:
    """RFM rule: >= min_visits in the previous `lookback_days`, none in the last `quiet_days`."""
    start = datetime.combine(today - timedelta(days=lookback_days), time.min)
    end = datetime.combine(today, time.min)
    quiet_start = datetime.combine(today - timedelta(days=quiet_days), time.min)
    stmt = (
        select(Transaction.payer_hash, func.count().label("visits"), func.max(Transaction.ts).label("last"))
        .where(Transaction.merchant_id == merchant_id, Transaction.direction == "in",
               Transaction.source.in_(VISIT_SOURCES), Transaction.ts >= start, Transaction.ts < end,
               Transaction.payer_hash.is_not(None))
        .group_by(Transaction.payer_hash)
        .having(func.count() >= min_visits)
    )
    rows = {h: (n, last) for h, n, last in session.exec(stmt)}
    lapsed_hashes = {h for h, (_, last) in rows.items() if _as_dt(last) < quiet_start}
    if not lapsed_hashes:
        return []
    customers = session.exec(select(Customer).where(Customer.merchant_id == merchant_id,
                                                    Customer.payer_hash.in_(lapsed_hashes))).all()
    out = []
    for c in customers:
        n, last = rows[c.payer_hash]
        last_dt = _as_dt(last)
        out.append({"customer_id": c.id, "name": c.name, "visits_90d": n,
                    "last_visit": last_dt.date().isoformat(), "days_since": (today - last_dt.date()).days,
                    "opted_in": c.opted_in})
    return sorted(out, key=lambda r: r["days_since"])


def _as_dt(v) -> datetime:
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))


# ---------------------------------------------------------------- peak hours / slow days

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _hour_label(h: int) -> str:
    def one(x: int) -> str:
        x12 = x % 12 or 12
        return f"{x12}"
    part = "subah" if h < 12 else ("dopahar" if h < 16 else ("shaam" if h < 20 else "raat"))
    return f"{part} {one(h)}-{one(h + 1)} baje"


def peak_heatmap(session: Session, merchant_id: int, today: date, weeks: int = 8) -> dict:
    """Average inflow per (weekday, hour) over the last `weeks` full weeks."""
    start = datetime.combine(today - timedelta(days=7 * weeks), time.min)
    end = datetime.combine(today, time.min)
    rows = session.exec(
        select(func.strftime("%w", Transaction.ts), func.strftime("%H", Transaction.ts),
               func.sum(Transaction.amount), func.count())
        .where(Transaction.merchant_id == merchant_id, Transaction.direction == "in",
               Transaction.ts >= start, Transaction.ts < end)
        .group_by(func.strftime("%w", Transaction.ts), func.strftime("%H", Transaction.ts))
    ).all()
    cells = []
    for w, h, total, n in rows:
        wd = (int(w) - 1) % 7  # sqlite: 0 = Sunday -> python: 6
        cells.append({"weekday": wd, "weekday_name": WEEKDAY_NAMES[wd], "hour": int(h),
                      "avg_sales": int(round(total / weeks)), "avg_txns": round(n / weeks, 1)})
    cells.sort(key=lambda c: (c["weekday"], c["hour"]))
    by_hour: dict[int, int] = {}
    for c in cells:
        by_hour[c["hour"]] = by_hour.get(c["hour"], 0) + c["avg_sales"]
    peak_h = max(by_hour, key=by_hour.get) if by_hour else None
    peak_cell = max(cells, key=lambda c: c["avg_sales"]) if cells else None
    return {
        "weeks": weeks, "cells": cells,
        "hours": sorted(by_hour),
        "peak_hour": peak_h, "peak_hour_label": _hour_label(peak_h) if peak_h is not None else None,
        "peak_hour_avg_daily_sales": int(round(by_hour[peak_h] / 7)) if peak_h is not None else None,
        "peak_slot": peak_cell and {"weekday_name": peak_cell["weekday_name"], "hour": peak_cell["hour"],
                                    "label": f"{peak_cell['weekday_name']} {_hour_label(peak_cell['hour'])}",
                                    "avg_sales": peak_cell["avg_sales"]},
    }


def slow_days(session: Session, merchant_id: int, today: date, weeks: int = 8) -> dict:
    from app.services.sales import daily_inflows

    data = daily_inflows(session, merchant_id, today - timedelta(days=7 * weeks), today)
    sums = {i: [] for i in range(7)}
    for d, v in data.items():
        sums[d.weekday()].append(v)
    avgs = {i: int(round(sum(v) / len(v))) for i, v in sums.items() if v}
    overall = int(round(sum(avgs.values()) / len(avgs)))
    ranked = sorted(avgs, key=avgs.get)
    slowest = ranked[0]
    return {
        "weeks": weeks, "overall_avg": overall,
        "by_weekday": [{"weekday": i, "weekday_name": WEEKDAY_NAMES[i], "avg_sales": avgs[i],
                        "vs_avg_pct": int(round((avgs[i] - overall) * 100 / overall))} for i in range(7)],
        "slowest": {"weekday_name": WEEKDAY_NAMES[slowest], "avg_sales": avgs[slowest],
                    "below_avg_pct": int(round((overall - avgs[slowest]) * 100 / overall))},
        "busiest": {"weekday_name": WEEKDAY_NAMES[ranked[-1]], "avg_sales": avgs[ranked[-1]]},
    }


def festival_comparison(session: Session, merchant_id: int, today: date) -> dict | None:
    """Most recent festival vs the same festival last year (lead-up days + festival days)."""
    from app.services.festivals import most_recent_festival, same_festival_last_year
    from app.services.sales import daily_inflows

    recent = most_recent_festival(today)
    if recent is None:
        return None
    this, prev = same_festival_last_year(recent.name, today)
    if prev is None:
        return None

    def window_total(f) -> tuple[int, int]:
        data = daily_inflows(session, merchant_id, f.window_start, f.end + timedelta(days=1))
        return sum(data.values()), len(data)

    t_total, n_days = window_total(this)
    p_total, _ = window_total(prev)
    if p_total == 0:
        return None
    pct = int(round((t_total - p_total) * 100 / p_total))
    return {"festival": this.name, "this_year": {"start": this.window_start.isoformat(), "end": this.end.isoformat(),
                                                 "total": t_total},
            "last_year": {"start": prev.window_start.isoformat(), "end": prev.end.isoformat(), "total": p_total},
            "days": n_days, "change_pct": pct, "change_abs": t_total - p_total}


def growth_insights(session: Session, merchant_id: int, today: date) -> dict:
    from app.services.fmt import rupees

    heat = peak_heatmap(session, merchant_id, today)
    slow = slow_days(session, merchant_id, today)
    fest = festival_comparison(session, merchant_id, today)
    lapsed = lapsed_regulars(session, merchant_id, today)
    opted = [r for r in lapsed if r["opted_in"]]
    lines = []
    if heat["peak_hour_label"]:
        lines.append(f"Sabse zyada bikri {heat['peak_hour_label']} hoti hai.")
    lines.append(f"{slow['slowest']['weekday_name']} sabse dheema din hai, aam din se "
                 f"{slow['slowest']['below_avg_pct']}% kam.")
    if fest:
        direction = "zyada" if fest["change_pct"] >= 0 else "kam"
        lines.append(f"Is {fest['festival']} par bikri {rupees(fest['this_year']['total'])} rahi, pichhle saal se "
                     f"{abs(fest['change_pct'])}% {direction}.")
    if lapsed:
        lines.append(f"{len(lapsed)} regular grahak 3 hafte se nahi aaye; {len(opted)} ko offer bhej sakte hain.")
    return {"peak_hours": heat, "slow_days": slow, "festival": fest,
            "lapsed_regulars": {"count": len(lapsed), "opted_in_count": len(opted), "customers": lapsed},
            "summary_text": " ".join(lines)}
