from datetime import date, timedelta

from sqlmodel import Session, select

from app.db import get_engine
from app.models import Payable
from app.services.fmt import fmt_date, rupees
from app.services.forecast import baseline_days, mae_mape, project

DEMO = date(2026, 11, 15)


def test_rupee_formatting():
    assert rupees(22000) == "₹22,000"
    assert rupees(123456) == "₹1,23,456"
    assert rupees(-7637) == "-₹7,637"
    assert rupees(950) == "₹950"
    assert fmt_date(date(2026, 11, 20)) == "20 Nov (Friday)"


def test_mae_mape():
    r = mae_mape([100, 200], [110, 180])
    assert r == {"mae": 15, "mape": 10.0}


def test_baseline_same_day_last_week():
    series = {DEMO - timedelta(days=k): float(k) for k in range(1, 30)}
    pred = baseline_days(series, DEMO, 10)
    assert pred[0] == 7.0 and pred[6] == 1.0
    assert pred[7] == 7.0  # day 7 of the horizon repeats last week's same weekday


def test_projection_math_and_moves():
    fc = [{"date": DEMO + timedelta(days=k), "p10": 100.0, "p50": 200.0, "p90": 300.0} for k in range(3)]
    pays = [{"id": 1, "supplier": "X", "amount": 500, "due_date": DEMO + timedelta(days=1)}]
    days = project(1000, 700, fc, pays, DEMO)
    assert [d["balance_p10"] for d in days] == [1100, 700, 800]
    assert [d["balance_p50"] for d in days] == [1200, 900, 1100]
    assert [d["below_buffer"] for d in days] == [False, False, False]
    days = project(1000, 750, fc, pays, DEMO)
    assert [d["below_buffer"] for d in days] == [False, True, False]
    moved = project(1000, 750, fc, pays, DEMO, {1: DEMO + timedelta(days=2)})
    assert [d["balance_p10"] for d in moved] == [1100, 1200, 800]
    overdue = [{"id": 2, "supplier": "Y", "amount": 50, "due_date": DEMO - timedelta(days=3)}]
    assert project(1000, 0, fc, overdue, DEMO)[0]["payables_total"] == 50


def test_backtest_beats_baseline(client):
    r = client.get("/cash/backtest").json()
    assert r["n_points"] == 60 and r["beats_baseline"] is True
    assert r["model"]["mae"] < r["baseline"]["mae"] and r["model"]["mape"] < r["baseline"]["mape"]
    r2 = client.get("/cash/backtest", params={"merchant_id": 2}).json()
    assert r2["beats_baseline"] is True


def test_radar_flags_agarwal_shortfall(client, fresh_db):
    r = client.get("/cash/radar").json()
    assert len(r["days"]) == 14 and r["balance_now"] == 16000
    assert r["days"][0]["date"] == DEMO.isoformat()
    sf = r["shortfalls"][0]
    assert sf["days_ahead"] >= 3 and sf["date"] == (DEMO + timedelta(days=5)).isoformat()
    assert sf["cause"]["supplier"] == "Agarwal Traders" and sf["cause"]["amount"] == 22000
    assert all(not d["below_buffer"] for d in r["days"][:5])
    for d in r["days"]:
        assert d["inflow_p10"] <= d["inflow_p50"] <= d["inflow_p90"]
    assert "Agarwal Traders" in r["summary_text"] and "₹22,000" in r["summary_text"]


def test_moving_payable_to_suggested_date_clears_shortfall(client, fresh_db):
    r = client.get("/cash/radar").json()
    fix = r["shortfalls"][0]["fix"]
    assert fix["within_forecast"] is True
    what_if = client.get("/cash/radar", params={"move_payable_id": fix["payable_id"],
                                                "move_to": fix["move_to"]}).json()
    assert what_if["flagged_days"] == [] and what_if["shortfalls"] == []
    # And for real: update the payable, the radar is clear.
    with Session(get_engine()) as s:
        p = s.get(Payable, fix["payable_id"])
        p.due_date = date.fromisoformat(fix["move_to"])
        s.add(p)
        s.commit()
    assert client.get("/cash/radar").json()["flagged_days"] == []
    # The day before the suggested date would not have been safe.
    earlier = (date.fromisoformat(fix["move_to"]) - timedelta(days=1)).isoformat()
    with Session(get_engine()) as s:
        p = s.get(Payable, fix["payable_id"])
        p.due_date = date.fromisoformat(earlier)
        s.add(p)
        s.commit()
    assert client.get("/cash/radar").json()["flagged_days"] != []


def test_radar_lakshmi_has_no_shortfall(client):
    r = client.get("/cash/radar", params={"merchant_id": 2}).json()
    assert r["shortfalls"] == [] and "upar rahega" in r["summary_text"]


def test_payment_today_reduces_remaining_forecast(client, fresh_db):
    before = client.get("/cash/radar").json()
    client.post("/demo/simulate-payment", json={"amount": 500, "payer_name": "Sunita"})
    after = client.get("/cash/radar").json()
    assert after["balance_now"] == before["balance_now"] + 500
    assert after["days"][0]["inflow_p50"] == max(before["days"][0]["inflow_p50"] - 500, 0)
    with Session(get_engine()) as s:
        assert s.exec(select(Payable).where(Payable.status == "scheduled")).first() is not None
