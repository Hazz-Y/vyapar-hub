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
