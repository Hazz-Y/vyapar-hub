from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app import clock, scheduler
from app.agent.tools import TOOLS, ToolContext
from app.db import get_engine
from app.models import Customer, Merchant, MessageLog, Payable, PendingAction, Settings, Transaction, Udhaar
from app.services.executor import ApprovalError, execute
from app.services.gst import month_range, split_tax
from app.services.matching import match_ledger

DEMO = date(2026, 11, 15)
FRIDAY = date(2026, 11, 20)
PIN = {"pin": "1234"}


def chat(client, msg):
    return client.post("/agent/chat", json={"message": msg}).json()


def set_autonomy(**kw):
    with Session(get_engine()) as s:
        row = s.get(Settings, 1)
        for k, v in kw.items():
            setattr(row, k, v)
        s.add(row)
        s.commit()


# ---------------------------------------------------------------- approve / reject


def test_wrong_pin_is_refused_and_locks_after_five(client, fresh_db):
    aid = chat(client, "Sharma ji ko 5000 bhejo")["pending_actions"][0]["id"]
    for i in range(4):
        r = client.post(f"/actions/{aid}/approve", json={"pin": "0000"})
        assert r.status_code == 403
    r = client.post(f"/actions/{aid}/approve", json={"pin": "9999"})
    assert r.status_code == 403 and "radd" in r.json()["detail"]
    assert client.get(f"/actions/{aid}").json()["status"] == "rejected"
    assert client.post(f"/actions/{aid}/approve", json=PIN).status_code == 409


def test_pay_supplier_on_approval_only(client, fresh_db):
    before = client.get("/cash/radar").json()["balance_now"]
    aid = chat(client, "Sharma ji ko 5000 bhejo")["pending_actions"][0]["id"]
    assert client.get("/cash/radar").json()["balance_now"] == before  # drafting moved nothing
    r = client.post(f"/actions/{aid}/approve", json=PIN).json()
    assert r["status"] == "executed" and r["approved_by"] == "pin"
    assert "demo" in r["confirmation_text"] and r["soundbox_text"] == "Sharma Milk Dairy ko 5000 rupaye bheje gaye"
    assert r["audio"]["provider"] == "browser"  # no Sarvam key in tests -> browser voice
    assert client.get("/cash/radar").json()["balance_now"] == before - 5000
    txn = client.get("/transactions", params={"limit": 1, "direction": "out"}).json()[0]
    assert txn["amount"] == 5000 and txn["counterparty"] == "Sharma Milk Dairy"
    assert client.post(f"/actions/{aid}/approve", json=PIN).status_code == 409  # no double execution


def test_reschedule_approval_clears_radar(client, fresh_db):
    assert client.get("/cash/radar").json()["flagged_days"]
    aid = chat(client, "Agarwal ka payment aage kar do")["pending_actions"][0]["id"]
    r = client.post(f"/actions/{aid}/approve", json=PIN).json()
    assert r["status"] == "executed" and "Agarwal Traders" in r["confirmation_text"]
    radar = client.get("/cash/radar").json()
    assert radar["flagged_days"] == [] and radar["shortfalls"] == []
    agarwal = [p for p in client.get("/payables").json() if p["supplier"] == "Agarwal Traders"][0]
    assert agarwal["status"] == "rescheduled" and agarwal["original_due_date"] == (DEMO + timedelta(days=5)).isoformat()
    events = client.get("/soundbox/events").json()
    assert any("shift ho gaya" in e["text"] for e in events)


def test_reject_discards(client, fresh_db):
    aid = chat(client, "Agarwal ka payment 7 tareekh ko kar do")["pending_actions"][0]["id"]
    r = client.post(f"/actions/{aid}/reject").json()
    assert r["action"]["status"] == "rejected"
    assert client.get("/cash/radar").json()["flagged_days"]  # unchanged
    assert client.post(f"/actions/{aid}/approve", json=PIN).status_code == 409
    assert client.post(f"/actions/{aid}/reject").status_code == 409
    assert client.post("/actions/99999/approve", json=PIN).status_code == 404


def test_pending_list(client, fresh_db):
    chat(client, "Sharma ji ko 5000 bhejo")
    pend = client.get("/actions").json()
    assert len(pend) == 1 and pend[0]["kind"] == "pay_supplier" and pend[0]["amount"] == 5000


def test_payments_never_auto_approved(client, fresh_db):
    set_autonomy(autonomy_supplier="auto", autonomy_cash="auto")
    r = chat(client, "Sharma ji ko 5000 bhejo")
    assert r["pending_actions"][0]["status"] == "pending"
    with Session(get_engine()) as s:
        pa = s.get(PendingAction, r["pending_actions"][0]["id"])
        with pytest.raises(ApprovalError):
            execute(s, pa, clock.now(), approved_by="auto")


# ---------------------------------------------------------------- udhaar


def test_log_udhaar_new_customer_on_approval(client, fresh_db):
    r = chat(client, "Bablu ji ne 300 ka udhaar liya, kal tak denge")
    assert r["pending_actions"] == []  # needs a phone first
    r = client.post("/agent/chat", json={"message": "x"})  # unrelated turn keeps working
    with Session(get_engine()) as s:
        ctx = ToolContext(session=s, merchant=s.get(Merchant, 1), now=clock.now(), today=clock.today(),
                          demo_start=clock.demo_start())
        res = TOOLS["log_udhaar"].run(ctx, {"customer_name": "Bablu", "amount": 300, "due": "kal",
                                           "phone": "+919000000002"})
    aid = res["pending_action_id"]
    out = client.post(f"/actions/{aid}/approve", json=PIN).json()
    assert "likh liya" in out["confirmation_text"]
    with Session(get_engine()) as s:
        c = s.exec(select(Customer).where(Customer.name == "Bablu")).one()
        assert c.phone == "+919000000002" and not c.opted_in
        u = s.exec(select(Udhaar).where(Udhaar.customer_id == c.id)).one()
        assert u.amount == 300 and u.due_date == DEMO + timedelta(days=1)


def test_sunita_full_flow_auto_close(client, fresh_db):
    r = chat(client, "Sunita ji ne 650 ka udhaar liya, Friday tak denge")
    assert r["reply_text"] == "₹650, Sunita ji, Friday (20 Nov) tak. Sahi hai?"
    out = client.post(f"/actions/{r['pending_actions'][0]['id']}/approve", json=PIN).json()
    assert "Sunita ji" in out["confirmation_text"]
    open_before = client.get("/udhaar", params={"status": "open"}).json()["entries"]
    assert sum(e["customer_name"] == "Sunita Verma" for e in open_before) == 1  # deduplicated
    pay = client.post("/demo/simulate-payment", json={"amount": 650, "payer_name": "Sunita ji"}).json()
    assert pay["settled_udhaar"]["customer"] == "Sunita ji"
    assert "udhaar band ho gaya" in pay["soundbox_text"]
    entries = client.get("/udhaar").json()["entries"]
    sunita = next(e for e in entries if e["customer_name"] == "Sunita Verma")
    assert sunita["status"] == "settled" and sunita["settled_txn_id"] == pay["transaction_id"]
    assert client.get("/soundbox/events").json()[-1]["text"].startswith("Paytm par 650 rupaye prapt hue")


def test_reminder_fires_on_due_date_at_ten_auto_mode(fresh_db):
    before_ten = datetime.combine(FRIDAY, datetime.min.time()).replace(hour=9, minute=59)
    out = scheduler.tick(before_ten)
    assert all(r["customer"] != "Sunita Verma" for r in out["reminders"])
    at_ten = before_ten.replace(hour=10, minute=0)
    out = scheduler.tick(at_ten)
    sunita = [r for r in out["reminders"] if r["customer"] == "Sunita Verma"]
    assert len(sunita) == 1 and sunita[0]["auto_sent"] is True
    with Session(get_engine()) as s:
        msgs = s.exec(select(MessageLog).where(MessageLog.kind == "udhaar_reminder")).all()
        body = next(m.body for m in msgs if "Sunita" in m.body)
        assert "upi://pay?pa=rameshkirana%40paytm" in body and "am=650.00" in body
        assert all(m.channel == "preview" for m in msgs)
        u = s.exec(select(Udhaar).join(Customer).where(Customer.name == "Sunita Verma")).one()
        assert u.status == "reminded" and u.reminded_at == at_ten
    again = scheduler.tick(at_ten + timedelta(minutes=1))
    assert again["reminders"] == []  # once per entry


def test_reminder_suggest_mode_creates_pending(fresh_db):
    set_autonomy(autonomy_udhaar="suggest")
    out = scheduler.tick(datetime(2026, 11, 20, 10, 0))
    assert out["reminders"] and not any(r["auto_sent"] for r in out["reminders"])
    with Session(get_engine()) as s:
        assert s.exec(select(MessageLog)).all() == []
        pend = s.exec(select(PendingAction).where(PendingAction.kind == "send_reminder",
                                                  PendingAction.status == "pending")).all()
        assert len(pend) == len(out["reminders"])
    assert scheduler.tick(datetime(2026, 11, 20, 10, 5))["reminders"] == []  # not re-drafted


def test_morning_briefing_scheduled_once_per_day(fresh_db):
    early = scheduler.tick(datetime(2026, 11, 15, 7, 59))["briefings"]
    assert 1 not in early and 2 in early  # Ramesh opens at 08:00, Lakshmi's tea stall at 06:00
    assert 1 in scheduler.tick(datetime(2026, 11, 15, 8, 0))["briefings"]
    assert 1 not in scheduler.tick(datetime(2026, 11, 15, 9, 0))["briefings"]


def test_briefing_today(client):
    b = client.get("/briefing/today").json()
    assert [c["kind"] for c in b["cards"]] == ["sales", "payments", "udhaar"]
    assert b["spoken_text"].startswith("Namaste Ramesh ji, Subah ki Report.")
    assert len(b["spoken_text"].split()) <= 80  # ~30 seconds spoken


# ---------------------------------------------------------------- growth


def test_growth_lapsed_and_winback(client, fresh_db):
    lapsed = client.get("/growth/lapsed").json()
    assert lapsed["count"] == 14
    r = client.post("/growth/winback/draft", json={"discount_pct": 10}).json()
    assert r["needs_approval"] is True and r["recipients"] == lapsed["opted_in_count"]
    out = client.post(f"/actions/{r['pending_action_id']}/approve", json=PIN).json()
    assert out["confirmation_text"].startswith(f"{lapsed['opted_in_count']} grahakon")
    with Session(get_engine()) as s:
        assert len(s.exec(select(MessageLog).where(MessageLog.kind == "winback")).all()) == lapsed["opted_in_count"]


def test_winback_rechecks_consent_at_send_time(client, fresh_db):
    r = client.post("/growth/winback/draft", json={}).json()
    with Session(get_engine()) as s:
        pa = s.get(PendingAction, r["pending_action_id"])
        c = s.get(Customer, pa.payload["customer_ids"][0])
        c.opted_in = False  # customer opts out before the merchant approves
        s.add(c)
        s.commit()
    out = client.post(f"/actions/{r['pending_action_id']}/approve", json=PIN).json()
    assert "1 ko nahi bheja" in out["confirmation_text"]


def test_growth_insights_endpoint(client):
    g = client.get("/growth/insights").json()
    assert len(g["peak_hours"]["cells"]) > 50 and g["festival"]["festival"] == "Diwali"
    assert g["lapsed_regulars"]["count"] == 14 and "14 regular grahak" in g["summary_text"]


# ---------------------------------------------------------------- suppliers: matching + GST


def test_split_tax():
    assert split_tax(1050, 5, True) == {"taxable_value": Decimal("1000.00"), "cgst": Decimal("25.00"),
                                         "sgst": Decimal("25.00"), "igst": Decimal("0.00")}
    t = split_tax(1000, 18, True)
    assert t["taxable_value"] == Decimal("847.46") and t["cgst"] + t["sgst"] == Decimal("152.54")
    assert split_tax(1180, 18, False)["igst"] == Decimal("180.00")
    assert split_tax(500, 0, True)["taxable_value"] == Decimal("500.00")


def test_month_range():
    assert month_range(None, DEMO) == (date(2026, 10, 1), date(2026, 11, 1))
    assert month_range("2026-02", DEMO) == (date(2026, 2, 1), date(2026, 3, 1))
    assert month_range("2026-12", DEMO) == (date(2026, 12, 1), date(2027, 1, 1))


def test_gst_export_csv(client):
    r = client.get("/suppliers/gst-export.csv", params={"month": "2026-10"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().split("\n")
    assert lines[0].startswith("invoice_date,invoice_no,supplier_name,supplier_gstin")
    rows = [dict(zip(lines[0].split(","), ln.split(","))) for ln in lines[1:]]
    assert rows and all(r["invoice_date"].startswith("2026-10") for r in rows)
    for row in rows:
        total = Decimal(row["invoice_total"])
        parts = Decimal(row["taxable_value"]) + Decimal(row["cgst"]) + Decimal(row["sgst"]) + Decimal(row["igst"])
        assert parts == total
    assert any(r["supplier_gstin"] == "UNREGISTERED" and r["itc_eligible"] == "no" for r in rows)


class FakeMatcher:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def match(self, rows, suppliers):
        self.calls.append((rows, suppliers))
        return self.answer(rows, suppliers)


def test_matching_fuzzy_then_llm_batch(fresh_db):
    with Session(get_engine()) as s:
        def answer(rows, suppliers):
            ids = {sp["name"]: sp["id"] for sp in suppliers}
            want = {"S.D. MILK": "Sharma Milk Dairy", "VA KNP DIST": "Verma Agencies", "M/S A.T. KNP": "Agarwal Traders"}
            out = {}
            for r in rows:
                out[r["row"]] = ids[want[r["text"]]] if r["text"] != "M/S A.T. KNP" else 999_999  # bogus id
            return out

        fake = FakeMatcher(answer)
        r = match_ledger(s, 1, limit=5000, llm=fake)
    assert len(fake.calls) == 1  # one batch
    sent = {row["text"] for row in fake.calls[0][0]}
    assert sent == {"S.D. MILK", "VA KNP DIST", "M/S A.T. KNP"}
    by_cp = {row["counterparty"]: row for row in r["rows"]}
    assert by_cp["S.D. MILK"]["supplier"] == "Sharma Milk Dairy" and by_cp["S.D. MILK"]["method"] == "llm"
    assert by_cp["M/S A.T. KNP"]["method"] == "unmatched"  # unknown id rejected
    assert by_cp["AGARWAL TRADERS KANPUR"]["method"] == "fuzzy" and by_cp["AGARWAL TRADERS KANPUR"]["score"] >= 85
    assert all(row["supplier"] is None or row["method"] in ("fuzzy", "llm") for row in r["rows"])


def test_matching_endpoint_without_llm(client):
    r = client.get("/suppliers/matching", params={"limit": 5000}).json()
    assert r["matched_fuzzy"] > 0 and r["llm_note"] == "LLM not configured: leftovers stay unmatched"


def test_payable_drafts_from_ui(client, fresh_db):
    agarwal = [p for p in client.get("/payables").json() if p["supplier"] == "Agarwal Traders"][0]
    r = client.post(f"/payables/{agarwal['id']}/reschedule/draft", json={}).json()
    assert r["clears_shortfall"] is True and r["pending_actions"][0]["kind"] == "reschedule_payable"
    r = client.post(f"/payables/{agarwal['id']}/pay/draft").json()
    assert r["pending_actions"][0]["payload"]["payable_id"] == agarwal["id"]
    with Session(get_engine()) as s:
        assert s.get(Payable, agarwal["id"]).status == "scheduled"  # still nothing executed
        assert s.exec(select(Transaction).where(Transaction.note.contains("approved action"))).all() == []
