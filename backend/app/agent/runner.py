"""Agent loop: LLM tool calling (Groq, or xAI Grok) with a rule-based fallback parser.

Both providers speak the OpenAI chat-completions protocol, so one client covers them.

Safety nets:
* max MAX_TOOL_CALLS tool calls per turn;
* number guard: every number in the final reply must appear in a tool result or the user's message,
  otherwise the reply is replaced by the tools' own ready-to-speak text.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from app.agent.prompts import system_prompt
from app.agent.tools import TOOLS, ToolContext, tool_schemas
from app.config import get_settings
from app.models import Settings
from app.services.actions import action_out
from app.services.customers import DEVANAGARI_NAMES
from app.services.numbers import words_to_digits

MAX_TOOL_CALLS = 5
DRAFT_TOOLS = {"draft_supplier_payment", "draft_reschedule_payable", "log_udhaar", "draft_udhaar_reminder",
               "draft_winback"}


# ---------------------------------------------------------------- LLM client


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    text: str
    calls: list[ToolCall] = field(default_factory=list)


class LLM(Protocol):
    def respond(self, *, messages: list[dict], tools: list[dict], tool_choice: str) -> LLMResponse: ...


class ChatClient:
    """OpenAI-compatible chat completions (Groq: api.groq.com/openai/v1, xAI: api.x.ai/v1)."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 25.0):
        from openai import OpenAI

        # No SDK retries: on a rate limit (free tier: 8k tokens/min) the rule-based parser answers at once
        # instead of the demo stalling on a retry-after wait.
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
        self.model = model

    def respond(self, *, messages, tools, tool_choice) -> LLMResponse:
        kwargs: dict[str, Any] = dict(model=self.model, messages=messages, tools=tools, tool_choice=tool_choice,
                                      temperature=0.2)
        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls = [ToolCall(tc.id, tc.function.name, tc.function.arguments or "{}") for tc in (msg.tool_calls or [])]
        return LLMResponse(msg.content or "", calls)


@lru_cache
def _cached_client(api_key: str, base_url: str, model: str) -> ChatClient:
    return ChatClient(api_key, base_url, model)  # reused: keeps the HTTPS connection warm between turns


def client_from_settings() -> ChatClient | None:
    s = get_settings()
    if s.llm_mode == "fallback":
        return None
    return _cached_client(s.llm_api_key, s.llm_base_url, s.llm_model)


# ---------------------------------------------------------------- number guard

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    out = set()
    for tok in _NUM.findall(text.translate(_DEVANAGARI_DIGITS)):
        tok = tok.replace(",", "").rstrip(".")
        try:
            v = float(tok)
        except ValueError:
            continue
        out.add(str(int(v)) if v.is_integer() else str(v))
    return out


def ungrounded_numbers(reply: str, sources: list[str]) -> set[str]:
    allowed = {"0", "1"}
    for s in sources:
        allowed |= numbers_in(s)
    return numbers_in(reply) - allowed


# ---------------------------------------------------------------- rule-based fallback parser

_DEVANAGARI_WORDS = {
    "को": "ko", "ने": "ne", "का": "ka", "की": "ki", "के": "ke", "उधार": "udhaar", "उधारी": "udhaar",
    "लिया": "liya", "लिए": "liye", "ली": "li", "तक": "tak", "देंगे": "denge", "देंगी": "dengi", "देगी": "degi",
    "देगा": "dega", "तारीख": "tareekh", "तारीख़": "tareekh", "पेमेंट": "payment", "भुगतान": "payment",
    "कर": "kar", "दो": "do", "दें": "de", "भेजो": "bhejo", "भेज": "bhej", "रुपये": "rupaye", "रुपए": "rupaye",
    "रुपया": "rupaye", "जी": "ji", "आज": "aaj", "कल": "kal", "परसों": "parson", "रिपोर्ट": "report",
    "ऑफर": "offer", "बिक्री": "bikri", "याद": "yaad", "दिलाओ": "dilao", "दिला": "dila", "हां": "haan",
    "हाँ": "haan", "सही": "sahi", "है": "hai", "ठीक": "theek", "कैश": "cash", "बैलेंस": "balance",
    "ग्राहक": "grahak", "रेगुलर": "regular", "सुबह": "subah", "रिमाइंडर": "reminder", "को।": "ko",
}


def normalise_utterance(text: str) -> str:
    from app.services.dates import WEEKDAY_LOOKUP, WEEKDAYS

    # The danda (।, ॥) lies inside the Devanagari block: strip it before word mapping ("देंगे।" -> "देंगे").
    t = re.sub(r"[।॥]", " ", text)
    t = words_to_digits(t.translate(_DEVANAGARI_DIGITS)).lower()
    t = re.sub(r"(?<=\d),(?=\d)", "", t).replace("₹", " ")

    def map_word(m: re.Match) -> str:
        w = m.group(0)
        if w in _DEVANAGARI_WORDS:
            return _DEVANAGARI_WORDS[w]
        if w in DEVANAGARI_NAMES:
            return DEVANAGARI_NAMES[w]
        wd = WEEKDAY_LOOKUP.get(w)
        return WEEKDAYS[wd][0] if wd is not None else w

    t = re.sub(r"[ऀ-ॿ]+", map_word, t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_NAME = r"(?P<name>[a-z]+(?: [a-z]+)?)(?: ji| didi| bhai| bhaiya| aunty)?"
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("reschedule_dom", re.compile(_NAME + r" (?:ka|ki|ke) (?:payment|bhugtan|bill|paisa) (?:ko )?"
                                          r"(?P<day>\d{1,2}) ?(?:tareekh|tarikh|tarik|th|st|nd|rd)?\b")),
    ("reschedule_when", re.compile(_NAME + r" (?:ka|ki|ke) (?:payment|bhugtan|bill) (?:ko )?(?P<when>kal|parson|"
                                           r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)")),
    ("reschedule_suggested", re.compile(_NAME + r" (?:ka|ki|ke) (?:payment|bhugtan|bill) (?:aage|baad|shift|"
                                                r"postpone|badha)")),
    ("udhaar", re.compile(_NAME + r" ne (?P<amt>\d+)(?: rupaye| rs| rupees)?(?: ka| ki| ke)? ?(?:udhaar|udhar|"
                                  r"udhari|credit) (?:liya|liye|li|le liya)(?: hai)?(?: aur)? (?P<due>.+?) (?:tak|ko) "
                                  r"(?:denge|dengi|dega|degi|de denge|de dengi|lautayenge|chuka)")),
    ("pay", re.compile(_NAME + r" ko (?P<amt>\d+)(?: rupaye| rs| rupees)? (?:bhejo|bhej do|de do|dedo|pay|"
                               r"transfer|bhej)")),
    ("reminder", re.compile(_NAME + r" ko (?:reminder|yaad|whatsapp)")),
]
_KEYWORDS = [
    ("confirm", re.compile(r"^(?:(?:haan|han|ha|ji|yes|sahi|hai|theek|thik|ok|okay|bilkul|kar|do)\s*)+$")),
    ("winback", re.compile(r"offer|win ?back|chhoot|discount")),
    ("briefing", re.compile(r"report|briefing|subah|aaj ka haal")),
    ("cash", re.compile(r"cash|balance|radar|paisa kam|kami|shortfall")),
    ("growth", re.compile(r"regular|grahak|customer|peak|festival|diwali|growth|dheema|slow")),
    ("udhaar_list", re.compile(r"udh?aa?r|udhari")),
    ("payables", re.compile(r"payment|supplier|due|bill")),
    ("sales", re.compile(r"bikri|sales|kitna bika|kamai|dhandha")),
]

HELP_TEXT = ("Main bikri, cash, udhaar, supplier payment aur grahakon mein madad kar sakta hoon. Jaise: "
             "'Sunita ji ne 650 ka udhaar liya, Friday tak denge'.")
CONFIRM_TEXT = "Theek hai. Screen par apna demo PIN daal kar approve kijiye."


def parse_intent(text: str) -> tuple[str, dict]:
    t = normalise_utterance(text)
    for name, pat in _PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        g = m.groupdict()
        if name == "reschedule_dom":
            return "draft_reschedule_payable", {"supplier_name": g["name"], "day_of_month": int(g["day"])}
        if name == "reschedule_when":
            return "draft_reschedule_payable", {"supplier_name": g["name"], "when": g["when"]}
        if name == "reschedule_suggested":
            return "draft_reschedule_payable", {"supplier_name": g["name"], "use_suggested_date": True}
        if name == "udhaar":
            return "log_udhaar", {"customer_name": g["name"], "amount": int(g["amt"]), "due": g["due"].strip()}
        if name == "pay":
            return "draft_supplier_payment", {"supplier_name": g["name"], "amount": int(g["amt"])}
        if name == "reminder":
            return "draft_udhaar_reminder", {"customer_name": g["name"]}
    for name, pat in _KEYWORDS:
        if pat.search(t):
            return {"confirm": "_confirm", "winback": "draft_winback", "briefing": "get_morning_briefing",
                    "cash": "get_cash_radar", "growth": "get_growth_insights", "udhaar_list": "list_udhaar",
                    "payables": "list_payables", "sales": "get_sales_summary"}[name], {}
    return "_help", {}


# ---------------------------------------------------------------- runner


def _run_tool(ctx: ToolContext, name: str, args: dict, source: str, trace: list) -> dict:
    t0 = time.perf_counter()
    tool = TOOLS.get(name)
    if tool is None:
        result = {"error": f"unknown tool {name}"}
    else:
        try:
            result = tool.run(ctx, args)
        except Exception as e:  # validation or lookup errors go back to the model
            result = {"error": type(e).__name__, "detail": str(e)[:300]}
    trace.append({"step": len(trace) + 1, "tool": name, "args": args, "result": result,
                  "ms": int((time.perf_counter() - t0) * 1000), "source": source})
    return result


def _spoken_from_trace(trace: list) -> str:
    parts = [t["result"].get("speak") for t in trace if isinstance(t.get("result"), dict) and t["result"].get("speak")]
    return " ".join(parts) or HELP_TEXT


def run_fallback(ctx: ToolContext, message: str, trace: list) -> str:
    name, args = parse_intent(message)
    if name == "_help":
        return HELP_TEXT
    if name == "_confirm":
        return CONFIRM_TEXT
    _run_tool(ctx, name, args, "rule-based", trace)
    return _spoken_from_trace(trace)


def run_llm(ctx: ToolContext, llm: LLM, message: str, history: list[dict], language: str, trace: list,
            source: str = "llm") -> str:
    tools = tool_schemas()
    messages: list[dict] = [{"role": "system", "content": system_prompt(ctx.merchant, ctx.today, language)}]
    messages += [{"role": h["role"], "content": h["content"]} for h in history[-10:]
                 if h.get("role") in ("user", "assistant") and h.get("content")]
    messages.append({"role": "user", "content": message})
    resp = llm.respond(messages=messages, tools=tools, tool_choice="auto")
    calls_made = 0
    while resp.calls:
        messages.append({"role": "assistant", "content": resp.text or None, "tool_calls": [
            {"id": c.call_id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in resp.calls]})
        step: list[tuple[str, dict]] = []
        for call in resp.calls:
            if calls_made >= MAX_TOOL_CALLS:
                result = {"error": "tool_call_limit", "detail": f"max {MAX_TOOL_CALLS} tool calls per turn"}
            else:
                try:
                    args = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _run_tool(ctx, call.name, args, source, trace)
                calls_made += 1
            step.append((call.name, result))
            messages.append({"role": "tool", "tool_call_id": call.call_id,
                             "content": json.dumps(result, ensure_ascii=False, default=str)})
        if all(name in DRAFT_TOOLS and "pending_action_id" in result for name, result in step):
            # Pure action turn: the read-back *is* the reply. Skips a second LLM call (latency + tokens).
            return " ".join(result["speak"] for _, result in step)
        choice = "none" if calls_made >= MAX_TOOL_CALLS else "auto"
        resp = llm.respond(messages=messages, tools=tools, tool_choice=choice)
    return resp.text.strip()


def run_agent(ctx: ToolContext, message: str, history: list[dict] | None = None, llm: LLM | None = None) -> dict:
    settings = get_settings()
    history = history or []
    row = ctx.session.get(Settings, ctx.merchant.id)
    language = row.language if row else ctx.merchant.language
    trace: list[dict] = []
    mode = "fallback"
    llm_name = "llm" if llm is not None else settings.llm_mode
    if llm is None:
        llm = client_from_settings()
    reply = ""
    if llm is not None:
        try:
            reply = run_llm(ctx, llm, message, history, language, trace, source=llm_name)
            mode = llm_name
        except Exception as e:
            trace.append({"step": len(trace) + 1, "tool": "llm_error", "args": {},
                          "result": {"error": type(e).__name__, "detail": str(e)[:300]}, "ms": 0,
                          "source": llm_name})
            reply = ""
    if mode == "fallback":
        reply = _spoken_from_trace(trace) if ctx.actions else run_fallback(ctx, message, trace)
    elif not reply:
        reply = _spoken_from_trace(trace)

    sources = [json.dumps(t["result"], ensure_ascii=False, default=str) for t in trace]
    sources += [message, HELP_TEXT, CONFIRM_TEXT]
    bad = ungrounded_numbers(reply, sources)
    if bad:
        trace.append({"step": len(trace) + 1, "tool": "number_guard", "args": {"reply": reply},
                      "result": {"ungrounded_numbers": sorted(bad), "action": "replaced reply with tool text"},
                      "ms": 0, "source": "guard"})
        reply = _spoken_from_trace(trace)
    return {"reply_text": reply, "pending_actions": [action_out(a) for a in ctx.actions], "tool_trace": trace,
            "mode": mode}
