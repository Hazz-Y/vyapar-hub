from datetime import date, datetime

from sqlmodel import Session, func, select

from app import clock
from app.db import get_engine
from app.models import Customer, MessageLog, Payable, Transaction, Udhaar
from app.services.timetravel import FILL_SOURCE, next_friday_10am

FRIDAY_10 = datetime(2026, 11, 20, 10, 0)


def test_next_friday_10am():
    assert next_friday_10am(datetime(2026, 11, 15, 8, 30)) == FRIDAY_10
    assert next_friday_10am(datetime(2026, 11, 20, 9, 59)) == FRIDAY_10
    assert next_friday_10am(datetime(2026, 11, 20, 10, 0)) == datetime(2026, 11, 27, 10, 0)


def test_state_after_reset(fresh_db, client):
    s = client.get("/demo/state").json()
    assert s["demo_date"] == "2026-11-15"
    assert s["day"] == 0
    assert s["next_jump"] == FRIDAY_10.isoformat()
    assert s["open_udhaar"] == 10
    assert s["pending_actions"] == 0


def test_jump_to_friday_moves_clock_and_sends_sunita_reminder(fresh_db, client):
    r = client.post("/demo/jump-to-friday").json()
    assert r["to"] == FRIDAY_10.isoformat()
    assert clock.now() >= FRIDAY_10
    assert client.get("/demo/state").json()["day"] == 5
    with Session(get_engine()) as s:
        sunita = s.exec(select(Customer).where(Customer.merchant_id == 1, Customer.name.like("Sunita%"))).first()
        logs = s.exec(select(MessageLog).where(MessageLog.to == sunita.phone)).all()
    assert any("650" in m.body for m in logs), "Sunita's reminder preview should be logged"
    assert any(x["customer"].startswith("Sunita") for x in r["tick"]["reminders"])


def test_jump_fills_skipped_sales_deterministically(fresh_db, client):
    first = client.post("/demo/jump-to-friday").json()["filled"]
    assert first["1"]["sales_added"] > 0
    client.post("/demo/reset")
    again = client.post("/demo/jump-to-friday").json()["filled"]
    assert abs(again["1"]["sales_added"] - first["1"]["sales_added"]) <= 5
    assert again["1"]["bills_paid"] == first["1"]["bills_paid"]
    with Session(get_engine()) as s:
        total = s.exec(select(func.sum(Transaction.amount)).where(
            Transaction.merchant_id == 1, Transaction.source == FILL_SOURCE, Transaction.direction == "in")).one()
    assert total == again["1"]["sales_added"]


def test_jump_pays_routine_bills_but_not_fridays(fresh_db, client):
    client.post("/demo/jump-to-friday")
    with Session(get_engine()) as s:
        skipped = s.exec(select(Payable).where(Payable.merchant_id == 1, Payable.due_date < date(2026, 11, 20),
                                               Payable.due_date >= date(2026, 11, 15))).all()
        friday = s.exec(select(Payable).where(Payable.merchant_id == 1, Payable.due_date == date(2026, 11, 20))).all()
    assert skipped and all(p.status == "paid" for p in skipped)
    assert friday and all(p.status != "paid" for p in friday), "Friday's bills still need approval"


def test_jump_does_not_settle_udhaar(fresh_db, client):
    client.post("/demo/jump-to-friday")
    with Session(get_engine()) as s:
        settled = s.exec(select(Udhaar).where(Udhaar.merchant_id == 1, Udhaar.status == "settled")).all()
    assert settled == []
