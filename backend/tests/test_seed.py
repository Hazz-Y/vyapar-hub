import time
from datetime import date, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_engine
from app.models import Customer, Merchant, Payable, Supplier, Transaction, Udhaar
from app.seed import HISTORY_DAYS, PESSIMISTIC_FACTOR, hash_payer, next_friday
from app.services.demo import reset_demo
from app.services.insights import lapsed_regulars

DEMO = date(2026, 11, 15)


def _count(s, model, *where):
    return s.exec(select(func.count()).select_from(model).where(*where)).one()


def test_seed_is_fast_and_deterministic():
    t0 = time.perf_counter()
    a = reset_demo()
    assert time.perf_counter() - t0 < 30
    b = reset_demo()
    assert a == b


def test_row_counts():
    with Session(get_engine()) as s:
        assert _count(s, Merchant) == 2
        for mid in (1, 2):
            assert _count(s, Customer, Customer.merchant_id == mid) == 400
            assert _count(s, Supplier, Supplier.merchant_id == mid) == 8
            days = s.exec(select(func.count(func.distinct(func.date(Transaction.ts))))
                          .where(Transaction.merchant_id == mid)).one()
            assert days == HISTORY_DAYS
        assert _count(s, Udhaar, Udhaar.merchant_id == 1, Udhaar.status == "open") == 10
        opted = _count(s, Customer, Customer.merchant_id == 1, Customer.opted_in == True)  # noqa: E712
        assert 200 <= opted <= 280  # ~60%


def test_history_ends_day_before_demo():
    with Session(get_engine()) as s:
        last = s.exec(select(func.max(Transaction.ts)).where(Transaction.merchant_id == 1)).one()
        assert last.date() == DEMO - timedelta(days=1)


def test_payer_ids_are_hashed():
    assert hash_payer("x@upi") != "x@upi" and len(hash_payer("x@upi")) == 20
    with Session(get_engine()) as s:
        hashes = s.exec(select(Transaction.payer_hash).where(Transaction.payer_hash.is_not(None)).limit(500)).all()
        assert all("@" not in h for h in hashes)


def test_sunita_udhaar_due_this_friday():
    with Session(get_engine()) as s:
        row = s.exec(select(Udhaar, Customer).join(Customer).where(Customer.name.startswith("Sunita"))).one()
        u, c = row
        assert u.amount == 650 and u.due_date == next_friday(DEMO) and u.status == "open"
        assert c.opted_in


def test_planted_shortfall_naive_projection():
    """Opening balance + 80% of a usual day - payables dips below buffer on day 5, not before."""
    with Session(get_engine()) as s:
        m = s.get(Merchant, 1)
        agarwal = s.exec(select(Payable).join(Supplier).where(
            Supplier.name == "Agarwal Traders", Payable.status == "scheduled")).one()
        assert agarwal.amount == 22_000 and agarwal.due_date == DEMO + timedelta(days=5)
        bal = m.opening_balance
        first_breach = None
        for k in range(14):
            d = DEMO + timedelta(days=k)
            same_wd = [x for x in (d - timedelta(days=7 * w) for w in range(1, 11)) if x < DEMO][:8]
            usual = sorted(
                s.exec(select(func.sum(Transaction.amount)).where(
                    Transaction.merchant_id == 1, Transaction.direction == "in",
                    func.date(Transaction.ts) == x.isoformat())).one() for x in same_wd)
            median = (usual[3] + usual[4]) / 2
            due = s.exec(select(func.coalesce(func.sum(Payable.amount), 0)).where(
                Payable.merchant_id == 1, Payable.status == "scheduled", Payable.due_date == d)).one()
            bal += PESSIMISTIC_FACTOR * median - due
            if bal < m.cash_buffer and first_breach is None:
                first_breach = k
        assert first_breach == 5


def test_fourteen_lapsed_regulars():
    with Session(get_engine()) as s:
        lapsed = lapsed_regulars(s, 1, DEMO)
    assert len(lapsed) == 14
    assert all(21 <= r["days_since"] <= 35 and r["visits_90d"] >= 4 for r in lapsed)
