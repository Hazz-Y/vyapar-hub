import statistics
from datetime import date, timedelta

from sqlmodel import Session

from app.db import get_engine
from app.services.customers import find_customer, normalise_name
from app.services.sales import day_totals, pct_change

DEMO = date(2026, 11, 15)


def test_status_reports_offline_modes(client):
    r = client.get("/status").json()
    assert r["llm"] == "fallback" and r["voice"] == "browser" and r["whatsapp"] == "preview"
    assert r["synthetic_data"] is True and r["demo_date"] == DEMO.isoformat()
    assert r["now"].startswith("2026-11-15T08:3")


def test_merchants_and_customers(client):
    ms = client.get("/merchants").json()
    assert [m["name"] for m in ms] == ["Ramesh Kirana Store", "Lakshmi Tea Stall"]
    assert client.get("/merchants/1").json()["upi_vpa"] == "rameshkirana@paytm"
    assert client.get("/merchants/99").status_code == 404
    cs = client.get("/customers", params={"limit": 10}).json()
    assert len(cs) == 10 and all("@" not in c["payer_hash"] for c in cs)


def test_settings_roundtrip(client, fresh_db):
    assert client.get("/settings").json()["autonomy_udhaar"] == "suggest"
    r = client.put("/settings", json={"autonomy_udhaar": "auto"})
    assert r.status_code == 200 and r.json()["autonomy_udhaar"] == "auto"
    assert client.put("/settings", json={"autonomy_udhaar": "yolo"}).status_code == 422


def test_messages_empty_after_reset(client, fresh_db):
    assert client.get("/messages").json() == []


def test_sales_summary_matches_db(client):
    r = client.get("/sales/summary").json()
    with Session(get_engine()) as s:
        y = day_totals(s, 1, DEMO - timedelta(days=1))
        samples = [day_totals(s, 1, DEMO - timedelta(days=1 + 7 * w))["total"] for w in range(1, 9)]
    assert r["today"]["total"] == 0
    assert r["yesterday"] == y
    assert r["usual_for_yesterday"] == int(round(statistics.median(samples)))
    assert r["yesterday_vs_usual_pct"] == pct_change(y["total"], r["usual_for_yesterday"])
    assert r["yesterday_weekday"] == "Saturday"


def test_pct_change():
    assert pct_change(110, 100) == 10
    assert pct_change(85, 100) == -15
    assert pct_change(5, 0) is None


def test_sales_daily_and_transactions(client):
    daily = client.get("/sales/daily", params={"days": 7}).json()
    assert len(daily) == 8 and daily[-1]["date"] == DEMO.isoformat()
    txns = client.get("/transactions", params={"limit": 5, "direction": "out"}).json()
    assert len(txns) == 5 and all(t["direction"] == "out" for t in txns)


def test_suppliers_and_payables(client):
    sups = client.get("/suppliers").json()
    assert len(sups) == 8
    pays = client.get("/payables").json()
    agarwal = [p for p in pays if p["supplier"] == "Agarwal Traders"]
    assert len(agarwal) == 1 and agarwal[0]["amount"] == 22000 and agarwal[0]["days_to_due"] == 5
    assert all(p["status"] == "scheduled" for p in pays)


def test_udhaar_list(client, fresh_db):
    r = client.get("/udhaar", params={"status": "open"}).json()
    assert len(r["entries"]) == 10
    assert r["totals"]["open_total"] == sum(e["amount"] for e in r["entries"])
    assert r["totals"]["due_today_or_overdue_count"] == 2


def test_udhaar_create_dedupes_and_requires_phone(client, fresh_db):
    friday = (DEMO + timedelta(days=5)).isoformat()
    r = client.post("/udhaar", json={"customer_name": "Sunita ji", "amount": 650, "due_date": friday})
    assert r.status_code == 201 and r.json()["created"] is False
    r = client.post("/udhaar", json={"customer_name": "Naya Grahak", "amount": 100, "due_date": friday})
    assert r.status_code == 422
    r = client.post("/udhaar", json={"customer_name": "Naya Grahak", "amount": 100, "due_date": friday,
                                     "phone": "+919000000001"})
    assert r.status_code == 201 and r.json()["created"] is True


def test_simulate_payment_closes_sunita_udhaar(client, fresh_db):
    r = client.post("/demo/simulate-payment", json={"amount": 650, "payer_name": "Sunita ji"}).json()
    assert r["settled_udhaar"]["customer"] == "Sunita ji"
    assert r["soundbox_text"].startswith("Paytm par 650 rupaye prapt hue")
    entries = client.get("/udhaar", params={"status": "settled"}).json()["entries"]
    assert [e["customer_name"] for e in entries] == ["Sunita Verma"]
    assert client.get("/sales/summary").json()["today"]["total"] == 650


def test_simulate_payment_unknown_payer(client):
    r = client.post("/demo/simulate-payment", json={"amount": 99, "payer_name": "Koi Nahi Xyz"})
    assert r.status_code == 404


def test_walkin_payment_does_not_close_udhaar(client, fresh_db):
    r = client.post("/demo/simulate-payment", json={"amount": 650, "payer_hash": "walkin-abc"}).json()
    assert r["settled_udhaar"] is None


def test_reset_restores_state(client):
    client.post("/demo/simulate-payment", json={"amount": 650, "payer_name": "Sunita"})
    r = client.post("/demo/reset").json()
    assert r["demo_date"] == DEMO.isoformat()
    assert len(client.get("/udhaar", params={"status": "open"}).json()["entries"]) == 10


def test_name_normalisation_and_lookup():
    assert normalise_name("Sunita ji") == "sunita"
    assert normalise_name("सुनीता जी") == "sunita"
    with Session(get_engine()) as s:
        assert find_customer(s, 1, "सुनीता जी").name == "Sunita Verma"
        assert find_customer(s, 1, "Suneeta ji").name == "Sunita Verma"
        assert find_customer(s, 1, "zzzz") is None
