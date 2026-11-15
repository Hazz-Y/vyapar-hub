"""Customer lookup by spoken name (handles honorifics and small spelling differences)."""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process
from sqlmodel import Session, select

from app.models import Customer

HONORIFICS = {"ji", "jee", "didi", "bhai", "bhaiya", "aunty", "auntie", "uncle", "bhabhi",
              "madam", "sir", "sahab", "saab", "जी", "दीदी", "भाई", "भैया", "आंटी"}

# Minimal Devanagari -> Roman map for names that appear in the demo.
DEVANAGARI_NAMES = {
    "सुनीता": "sunita", "अनीता": "anita", "मनोज": "manoj", "कमला": "kamla", "दीपक": "deepak",
    "गीता": "geeta", "राकेश": "rakesh", "सविता": "savita", "पंकज": "pankaj", "उषा": "usha",
    "शर्मा": "sharma", "अग्रवाल": "agarwal", "वर्मा": "verma", "गुप्ता": "gupta", "यादव": "yadav",
    "सिंह": "singh", "जैन": "jain", "मॉडर्न": "modern",
}


def normalise_name(name: str) -> str:
    words = re.findall(r"[\wऀ-ॿ]+", name.lower())
    words = [DEVANAGARI_NAMES.get(w, w) for w in words if w not in HONORIFICS]
    return " ".join(words)


def display_name(full_name: str) -> str:
    return f"{full_name.split()[0]} ji"


def find_customer(session: Session, merchant_id: int, spoken: str, threshold: int = 85) -> Customer | None:
    query = normalise_name(spoken)
    if not query:
        return None
    customers = session.exec(select(Customer).where(Customer.merchant_id == merchant_id)).all()
    full = {c.id: c.name.lower() for c in customers}
    exact = [c for c in customers if full[c.id] == query]
    if exact:
        return exact[0]
    first = [c for c in customers if full[c.id].split()[0] == query.split()[0]]
    if len(query.split()) == 1 and len(first) == 1:
        return first[0]
    if len(first) > 1 and len(query.split()) > 1:
        best = process.extractOne(query, {c.id: full[c.id] for c in first}, scorer=fuzz.token_set_ratio)
        if best and best[1] >= threshold:
            return next(c for c in first if c.id == best[2])
    if len(first) > 1:
        return None  # ambiguous: ask the merchant
    if len(query.split()) == 1:
        by_first: dict[str, list[Customer]] = {}
        for c in customers:
            by_first.setdefault(full[c.id].split()[0], []).append(c)
        scored = sorted(((fuzz.ratio(query, f), f) for f in by_first), reverse=True)
        if not scored:
            return None
        top, name = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0
        if top >= 75 and top - runner_up >= 8 and len(by_first[name]) == 1:
            return by_first[name][0]
        return None
    best = process.extractOne(query, full, scorer=fuzz.WRatio)
    if best and best[1] >= threshold:
        return next(c for c in customers if c.id == best[2])
    return None
