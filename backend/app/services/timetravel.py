"""Demo time travel: move the clock forward and fill the skipped hours with synthetic activity.

Skipped days get the usual sales for that weekday (deterministic, seeded) and their routine supplier
bills are marked paid in cash, so the radar doesn't show a fake crash from five days of nothing.
Payables due on the target day itself are left alone: those still need the merchant's approval.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np
from sqlmodel import Session, select

from app.models import Merchant, Payable, Supplier, Transaction
from app.seed import PROFILES, SEED, Profile
from app.services.sales import usual_day

FILL_SOURCE = "demo_fill"
REMINDER_HOUR = time(10, 0)


def next_friday_10am(now: datetime) -> datetime:
    """First Friday 10:00 strictly after now."""
    target = datetime.combine(now.date() + timedelta(days=(4 - now.weekday()) % 7), REMINDER_HOUR)
    return target if target > now else target + timedelta(days=7)


def _hour_share(start: datetime, end: datetime, h: int) -> float:
    """Fraction of clock hour h on start's date that falls inside [start, end)."""
    slot_start = datetime.combine(start.date(), time(h))
    lo, hi = max(start, slot_start), min(end, slot_start + timedelta(hours=1))
    return max(0.0, (hi - lo).total_seconds() / 3600)


def _fill_window(session: Session, merchant_id: int, p: Profile, start: datetime, end: datetime) -> int:
    """Insert synthetic QR inflows for one calendar-day window [start, end). Returns the rupees added."""
    hours = [h for h in p.hours if _hour_share(start, end, h) > 0]
    if not hours:
        return 0
    weights = np.array([p.hours[h] * _hour_share(start, end, h) for h in hours])
    share = weights.sum() / sum(p.hours.values())
    target = int(round(usual_day(session, merchant_id, start.date())["median"] * share))
    if target <= 0:
        return 0
    rng = np.random.default_rng(SEED + merchant_id * 100_003 + start.date().toordinal())
    n = max(1, int(round(target / p.walkin_ticket)))
    split = np.floor(rng.dirichlet(np.ones(n)) * target).astype(int)
    split[-1] += target - int(split.sum())
    for amount in split:
        if amount <= 0:
            continue
        h = int(rng.choice(hours, p=weights / weights.sum()))
        lo = max(start, datetime.combine(start.date(), time(h)))
        hi = min(end, datetime.combine(start.date(), time(h)) + timedelta(hours=1))
        ts = lo + timedelta(seconds=int(rng.integers(0, max(1, int((hi - lo).total_seconds())))))
        session.add(Transaction(merchant_id=merchant_id, ts=ts, amount=int(amount), direction="in",
                                source=FILL_SOURCE, note="Simulated sale (demo time skip)"))
    return target


def _settle_routine_bills(session: Session, merchant: Merchant, start: date, before: date) -> list[dict]:
    rows = session.exec(select(Payable, Supplier).join(Supplier).where(
        Payable.merchant_id == merchant.id, Payable.status.in_(("scheduled", "rescheduled")),
        Payable.due_date >= start, Payable.due_date < before).order_by(Payable.due_date, Payable.id)).all()
    paid = []
    for pay, sup in rows:
        txn = Transaction(merchant_id=merchant.id, ts=datetime.combine(pay.due_date, time(9, 0)),
                          amount=pay.amount, direction="out", counterparty=sup.name, source=FILL_SOURCE,
                          note="Paid in cash during the demo time skip (simulated)")
        session.add(txn)
        session.flush()
        pay.status, pay.paid_txn_id = "paid", txn.id
        session.add(pay)
        paid.append({"payable_id": pay.id, "supplier": sup.name, "amount": pay.amount,
                     "due_date": pay.due_date.isoformat()})
    return paid


def fill_until(session: Session, now: datetime, target: datetime) -> dict:
    """Fill every merchant's activity between now and target. Caller commits and moves the clock."""
    out = {}
    for merchant in session.exec(select(Merchant)).all():
        p = PROFILES[merchant.id - 1]
        sales, d = 0, now.date()
        while d <= target.date():
            lo = max(now, datetime.combine(d, time.min))
            hi = min(target, datetime.combine(d + timedelta(days=1), time.min))
            if hi > lo:
                sales += _fill_window(session, merchant.id, p, lo, hi)
            d += timedelta(days=1)
        bills = _settle_routine_bills(session, merchant, now.date(), target.date())
        out[merchant.id] = {"sales_added": sales, "bills_paid": len(bills),
                            "bills_paid_total": sum(b["amount"] for b in bills)}
    return out
