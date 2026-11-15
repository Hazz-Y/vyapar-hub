import copy
import json
from datetime import date

import pytest
from sqlmodel import Session, select

from app import clock
from app.agent.runner import (MAX_TOOL_CALLS, LLMResponse, ToolCall, numbers_in, parse_intent, run_agent,
                              ungrounded_numbers)
from app.agent.tools import TOOLS, ToolContext, tool_schemas
from app.db import get_engine
from app.models import Customer, Merchant, Payable, PendingAction, Udhaar
from app.services.dates import next_day_of_month, next_weekday, resolve_phrase
from app.services.suppliers import find_supplier

DEMO = date(2026, 11, 15)  # a Sunday


class FakeLLM:
    """Scripted LLM: returns the queued responses in order and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def respond(self, **kw):
        self.requests.append(copy.deepcopy(kw))  # snapshot: the runner keeps appending to `messages`
        return self.responses.pop(0)


def call(name, args, cid="c1"):
    return ToolCall(cid, name, json.dumps(args))


@pytest.fixture
def ctx(fresh_db):
    with Session(get_engine()) as s:
        m = s.get(Merchant, 1)
        yield ToolContext(session=s, merchant=m, now=clock.now(), today=clock.today(), demo_start=clock.demo_start())


# ---------------------------------------------------------------- unit: dates, lookup, guard


def test_date_resolution():
    assert next_weekday(DEMO, 4) == date(2026, 11, 20)
    assert next_weekday(date(2026, 11, 20), 4) == date(2026, 11, 27)
    assert next_day_of_month(DEMO, 7) == date(2026, 12, 7)
    assert next_day_of_month(DEMO, 20) == date(2026, 11, 20)
    assert next_day_of_month(date(2026, 1, 31), 31) == date(2026, 2, 28)
    assert resolve_phrase(DEMO, "Friday") == date(2026, 11, 20)
    assert resolve_phrase(DEMO, "शुक्रवार") == date(2026, 11, 20)
    assert resolve_phrase(DEMO, "kal") == date(2026, 11, 16)
    assert resolve_phrase(DEMO, "7 tareekh") == date(2026, 12, 7)
    assert resolve_phrase(DEMO, "10 din baad") == date(2026, 11, 25)
    assert resolve_phrase(DEMO, "2026-12-01") == date(2026, 12, 1)
    assert resolve_phrase(DEMO, "someday") is None


def test_supplier_lookup():
    with Session(get_engine()) as s:
        assert find_supplier(s, 1, "Sharma ji").name == "Sharma Milk Dairy"
        assert find_supplier(s, 1, "agarwal").name == "Agarwal Traders"
        assert find_supplier(s, 1, "अग्रवाल").name == "Agarwal Traders"
        assert find_supplier(s, 1, "Bilkul Anjaan") is None


def test_number_guard():
    assert numbers_in("₹22,000 aur ३ din, 12.50") == {"22000", "3", "12.5"}
    assert ungrounded_numbers("Kal ₹17,730 ki bikri", ['{"yesterday_total": "₹17,730"}']) == set()
    assert ungrounded_numbers("Kal ₹18,000 ki bikri", ['{"yesterday_total": "₹17,730"}']) == {"18000"}


def test_tool_schemas_are_objects():
    schemas = tool_schemas()
    assert {s["function"]["name"] for s in schemas} == {
        "get_sales_summary", "get_cash_radar", "list_payables", "draft_supplier_payment",
        "draft_reschedule_payable", "log_udhaar", "list_udhaar", "draft_udhaar_reminder", "get_growth_insights",
        "draft_winback", "get_morning_briefing"}
    for s in schemas:
        assert s["type"] == "function" and s["function"]["parameters"]["type"] == "object"
    log = next(s for s in schemas if s["function"]["name"] == "log_udhaar")["function"]["parameters"]
    assert set(log["required"]) == {"customer_name", "amount", "due"}


# ---------------------------------------------------------------- fallback parser


@pytest.mark.parametrize("text,tool,args", [
    ("Agarwal ka payment 7 tareekh ko kar do", "draft_reschedule_payable", {"day_of_month": 7}),
    ("अग्रवाल का पेमेंट 7 तारीख को कर दो", "draft_reschedule_payable", {"day_of_month": 7}),
    ("Sunita ji ne 650 ka udhaar liya, Friday tak denge", "log_udhaar", {"amount": 650, "due": "friday"}),
    ("सुनीता जी ने ६५० का उधार लिया, शुक्रवार तक देंगे", "log_udhaar", {"amount": 650, "due": "friday"}),
    # exactly as Saaras v3 codemix returns it: danda, mixed script, number words
    ("सुनीता जी ने छः सौ पचास का उधार लिया, Friday तक देंगे।", "log_udhaar", {"amount": 650, "due": "friday"}),
    ("अग्रवाल का payment 7 तारीख को कर दो।", "draft_reschedule_payable", {"day_of_month": 7}),
    ("शर्मा जी को पाँच हज़ार भेजो।", "draft_supplier_payment", {"amount": 5000}),
    ("Sharma ji ko 5,000 bhejo", "draft_supplier_payment", {"amount": 5000}),
    ("Sunita ji ko reminder bhejo", "draft_udhaar_reminder", {}),
    ("subah ki report sunao", "get_morning_briefing", {}),
    ("cash radar dikhao", "get_cash_radar", {}),
    ("haan sahi hai", "_confirm", {}),
    ("purane grahakon ko offer bhejo", "draft_winback", {}),
])
def test_parse_intent(text, tool, args):
    name, parsed = parse_intent(text)
    assert name == tool
    for k, v in args.items():
        assert parsed[k] == v


def test_fallback_reschedule_drafts_only(ctx):
    before = {p.id: (p.due_date, p.status) for p in ctx.session.exec(select(Payable)).all()}
    r = run_agent(ctx, "Agarwal ka payment 7 tareekh ko kar do")
    assert r["mode"] == "fallback"
    [a] = r["pending_actions"]
    assert a["kind"] == "reschedule_payable" and a["status"] == "pending"
    assert a["payload"]["new_due_date"] == "2026-12-07" and a["payload"]["amount"] == 22000
    assert r["reply_text"].endswith("Sahi hai?") and "₹22,000" in r["reply_text"]
    assert r["tool_trace"][0]["tool"] == "draft_reschedule_payable"
    after = {p.id: (p.due_date, p.status) for p in ctx.session.exec(select(Payable)).all()}
    assert before == after  # nothing executed


def test_fallback_udhaar_readback(ctx):
    n_before = len(ctx.session.exec(select(Udhaar)).all())
    r = run_agent(ctx, "Sunita ji ne 650 ka udhaar liya, Friday tak denge")
    assert r["reply_text"] == "₹650, Sunita ji, Friday (20 Nov) tak. Sahi hai?"
    assert r["pending_actions"][0]["kind"] == "log_udhaar"
    assert len(ctx.session.exec(select(Udhaar)).all()) == n_before


def test_fallback_new_customer_needs_phone(ctx):
    r = run_agent(ctx, "Bablu ji ne 300 ka udhaar liya, kal tak denge")
    assert r["pending_actions"] == [] and "phone" in r["reply_text"]


def test_fallback_help(ctx):
    r = run_agent(ctx, "namaste")
    assert r["tool_trace"] == [] and "madad" in r["reply_text"]


# ---------------------------------------------------------------- mocked LLM tool loop


def test_llm_tool_loop_message_format(ctx):
    llm = FakeLLM([
        LLMResponse("", [call("get_sales_summary", {})]),
        LLMResponse("Kal ki bikri theek rahi."),
    ])
    r = run_agent(ctx, "kal kitni bikri hui?", llm=llm, history=[{"role": "user", "content": "namaste"},
                                                                 {"role": "assistant", "content": "Namaste ji"}])
    assert r["mode"] == "llm" and r["reply_text"] == "Kal ki bikri theek rahi."
    first, second = llm.requests
    assert first["messages"][0]["role"] == "system"
    assert "Use ONLY numbers that appear in tool results" in first["messages"][0]["content"]
    assert [m["role"] for m in first["messages"]] == ["system", "user", "assistant", "user"]
    assert first["messages"][-1] == {"role": "user", "content": "kal kitni bikri hui?"}
    assistant, tool_msg = second["messages"][-2:]
    assert assistant["tool_calls"][0]["id"] == "c1"
    assert assistant["tool_calls"][0]["function"]["name"] == "get_sales_summary"
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert "speak" in json.loads(tool_msg["content"])


def test_llm_draft_turn_replies_with_readback_in_one_call(ctx):
    llm = FakeLLM([
        LLMResponse("", [call("log_udhaar", {"customer_name": "Sunita ji", "amount": 650, "due": "Friday"})]),
    ])
    r = run_agent(ctx, "Sunita ji ne 650 ka udhaar liya, Friday tak denge", llm=llm)
    assert len(llm.requests) == 1  # no second LLM call: the read-back is the reply
    assert r["reply_text"] == "₹650, Sunita ji, Friday (20 Nov) tak. Sahi hai?"
    assert [t["tool"] for t in r["tool_trace"]] == ["log_udhaar"]
    assert r["pending_actions"][0]["status"] == "pending"


def test_llm_failed_draft_goes_back_to_model(ctx):
    llm = FakeLLM([
        LLMResponse("", [call("draft_supplier_payment", {"supplier_name": "Bilkul Anjaan", "amount": 100})]),
        LLMResponse("Yeh supplier nahi mila. Kaun sa supplier?"),
    ])
    r = run_agent(ctx, "Bilkul Anjaan ko 100 bhejo", llm=llm)
    assert len(llm.requests) == 2 and r["pending_actions"] == []


def test_llm_tool_call_limit(ctx):
    many = [call("get_sales_summary", {}, f"c{i}") for i in range(3)]
    llm = FakeLLM([LLMResponse("", many), LLMResponse("", many), LLMResponse("Theek hai.")])
    r = run_agent(ctx, "sab batao", llm=llm)
    real = [t for t in r["tool_trace"] if t["tool"] == "get_sales_summary"]
    assert len(real) == MAX_TOOL_CALLS
    assert llm.requests[-1]["tool_choice"] == "none"
    limited = [json.loads(m["content"]) for m in llm.requests[-1]["messages"] if m["role"] == "tool"]
    assert any(o.get("error") == "tool_call_limit" for o in limited)


def test_llm_invented_number_is_replaced(ctx):
    llm = FakeLLM([LLMResponse("", [call("get_sales_summary", {})]),
                   LLMResponse("Kal ₹99,999 ki bikri hui!")])
    r = run_agent(ctx, "kal kitni bikri hui", llm=llm)
    assert "99,999" not in r["reply_text"]
    assert r["reply_text"] == r["tool_trace"][0]["result"]["speak"]
    assert r["tool_trace"][-1]["tool"] == "number_guard"


def test_llm_bad_args_are_reported_back(ctx):
    llm = FakeLLM([LLMResponse("", [call("draft_supplier_payment", {"supplier_name": "Sharma", "amount": -5})]),
                   LLMResponse("Amount sahi nahi hai, phir se batayein.")])
    r = run_agent(ctx, "Sharma ko bhejo", llm=llm)
    assert r["tool_trace"][0]["result"]["error"] == "ValidationError"
    assert r["pending_actions"] == []


def test_llm_error_falls_back_to_rules(ctx):
    class Broken:
        def respond(self, **kw):
            raise ConnectionError("xAI unreachable")

    r = run_agent(ctx, "Sharma ji ko 5000 bhejo", llm=Broken())
    assert r["mode"] == "fallback"
    assert r["tool_trace"][0]["tool"] == "llm_error"
    assert r["pending_actions"][0]["kind"] == "pay_supplier"


def test_winback_only_opted_in(ctx):
    r = TOOLS["draft_winback"].run(ctx, {})
    pa = ctx.session.get(PendingAction, r["pending_action_id"])
    for cid in pa.payload["customer_ids"]:
        assert ctx.session.get(Customer, cid).opted_in
    assert pa.payload["count"] + pa.payload["skipped_not_opted_in"] == 14


def test_reminder_contains_upi_link(ctx):
    r = TOOLS["draft_udhaar_reminder"].run(ctx, {"customer_name": "Sunita ji"})
    assert "upi://pay?pa=rameshkirana%40paytm&pn=Ramesh%20Kirana%20Store&am=650.00&cu=INR" in r["message_preview"]


def test_chat_endpoint(client, fresh_db):
    r = client.post("/agent/chat", json={"message": "Sharma ji ko 5000 bhejo"}).json()
    assert set(r) == {"reply_text", "pending_actions", "tool_trace", "mode"}
    assert r["pending_actions"][0]["amount"] == 5000
