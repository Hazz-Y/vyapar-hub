"""Match payment records (outflow counterparty strings) to suppliers.

1. rapidfuzz token_set_ratio against the supplier name, the name without generic words
   ("Dairy", "Traders"...), and the UPI handle; accept at >= THRESHOLD.
2. Leftovers go to the LLM in ONE batch with the supplier list. Only supplier ids that exist in that
   list are accepted back; anything else stays unmatched.
"""
from __future__ import annotations

import json
import re
from typing import Protocol

from rapidfuzz import fuzz
from sqlmodel import Session, select

from app.models import Supplier, Transaction
from app.services.suppliers import GENERIC

THRESHOLD = 85
_EXTRA_GENERIC = {"kanpur", "knp", "chennai", "pvt", "ltd", "dist", "distributor", "bhandar", "m", "s", "the"}


class BatchLLM(Protocol):
    def match(self, rows: list[dict], suppliers: list[dict]) -> dict[str, int | None]: ...


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _core(text: str) -> str:
    return " ".join(w for w in _clean(text).split() if w not in GENERIC and w not in _EXTRA_GENERIC)


def score(counterparty: str, sup: Supplier) -> int:
    cp = counterparty.lower()
    if "@" in cp:  # a UPI handle: compare the local part with the supplier's handle / squashed name
        local = cp.split("@")[0]
        cands = [sup.upi_vpa.lower().split("@")[0], _clean(sup.name).replace(" ", "")]
        return int(max(fuzz.ratio(local, c) for c in cands))
    full = fuzz.token_set_ratio(_clean(counterparty), _clean(sup.name))
    core_cp, core_sup = _core(counterparty), _core(sup.name)
    core = fuzz.token_set_ratio(core_cp, core_sup) if core_cp and core_sup else 0
    return int(max(full, core))


def fuzzy_match(counterparty: str, suppliers: list[Supplier]) -> tuple[Supplier | None, int]:
    best = max(((score(counterparty, s), s) for s in suppliers), key=lambda x: x[0], default=(0, None))
    return (best[1], best[0]) if best[0] >= THRESHOLD else (None, best[0])


class LLMBatchMatcher:
    """Sends unmatched strings to the configured LLM (Groq / Grok) as one JSON request."""

    def __init__(self, chat_client):
        self.chat = chat_client

    def match(self, rows: list[dict], suppliers: list[dict]) -> dict[str, int | None]:
        prompt = (
            "Match each bank/UPI payment description to one supplier id from the list, or null if unsure. "
            "Reply with JSON only: {\"matches\": [{\"row\": <row key>, \"supplier_id\": <id or null>}]}\n"
            f"Suppliers: {json.dumps(suppliers, ensure_ascii=False)}\nRows: {json.dumps(rows, ensure_ascii=False)}")
        resp = self.chat.client.chat.completions.create(
            model=self.chat.model, messages=[{"role": "user", "content": prompt}], temperature=0,
            response_format={"type": "json_object"})
        data = json.loads(resp.choices[0].message.content or "{}")
        return {str(m.get("row")): m.get("supplier_id") for m in data.get("matches", []) if isinstance(m, dict)}


def match_ledger(session: Session, merchant_id: int, limit: int = 300, llm: BatchLLM | None = None) -> dict:
    suppliers = list(session.exec(select(Supplier).where(Supplier.merchant_id == merchant_id)).all())
    by_id = {s.id: s for s in suppliers}
    txns = session.exec(select(Transaction).where(
        Transaction.merchant_id == merchant_id, Transaction.direction == "out",
        Transaction.source == "supplier_payment").order_by(Transaction.ts.desc()).limit(limit)).all()

    # Match each distinct counterparty string once.
    strings: dict[str, list[Transaction]] = {}
    for t in txns:
        strings.setdefault(t.counterparty or "", []).append(t)
    results: dict[str, dict] = {}
    leftovers = []
    for cp in strings:
        sup, sc = fuzzy_match(cp, suppliers)
        if sup:
            results[cp] = {"supplier_id": sup.id, "supplier": sup.name, "method": "fuzzy", "score": sc}
        else:
            leftovers.append(cp)
            results[cp] = {"supplier_id": None, "supplier": None, "method": "unmatched", "score": sc}

    llm_note = None
    if leftovers:
        if llm is None:
            from app.agent.runner import client_from_settings

            client = client_from_settings()
            llm = LLMBatchMatcher(client) if client else None
        if llm is None:
            llm_note = "LLM not configured: leftovers stay unmatched"
        else:
            rows = [{"row": str(i), "text": cp} for i, cp in enumerate(leftovers)]
            try:
                answer = llm.match(rows, [{"id": s.id, "name": s.name, "category": s.category} for s in suppliers])
            except Exception as e:
                answer, llm_note = {}, f"LLM batch failed: {type(e).__name__}"
            for i, cp in enumerate(leftovers):
                sid = answer.get(str(i))
                if isinstance(sid, int) and sid in by_id:  # accept only exact ids from our list
                    results[cp] = {"supplier_id": sid, "supplier": by_id[sid].name, "method": "llm",
                                   "score": results[cp]["score"]}

    rows = [{"counterparty": cp, "count": len(ts), "total": sum(t.amount for t in ts), **results[cp]}
            for cp, ts in strings.items()]
    rows.sort(key=lambda r: (r["method"] != "unmatched", -r["count"]))
    counts = {m: sum(r["count"] for r in rows if r["method"] == m) for m in ("fuzzy", "llm", "unmatched")}
    return {"threshold": THRESHOLD, "transactions": len(txns), "distinct_counterparties": len(rows),
            "matched_fuzzy": counts["fuzzy"], "matched_llm": counts["llm"], "unmatched": counts["unmatched"],
            "llm_note": llm_note, "rows": rows}
