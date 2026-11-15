"""Supplier lookup by spoken name ("Sharma ji", "Agarwal", "अग्रवाल")."""
from __future__ import annotations

from rapidfuzz import fuzz
from sqlmodel import Session, select

from app.models import Supplier
from app.services.customers import normalise_name

GENERIC = {"traders", "trader", "agencies", "agency", "store", "stores", "mills", "mill", "dairy", "milk",
           "bakery", "beverages", "namkeen", "atta", "chakki", "depot", "provisions", "wale", "wala", "waale"}


def find_supplier(session: Session, merchant_id: int, spoken: str, threshold: int = 80) -> Supplier | None:
    query = normalise_name(spoken)
    if not query:
        return None
    q_tokens = [t for t in query.split() if t not in GENERIC] or query.split()
    suppliers = session.exec(select(Supplier).where(Supplier.merchant_id == merchant_id)).all()
    scored = []
    for s in suppliers:
        tokens = (s.name + " " + s.contact_name).lower().split()
        token_score = max((fuzz.ratio(q, t) for q in q_tokens for t in tokens), default=0)
        full_score = fuzz.token_set_ratio(query, s.name.lower())
        scored.append((max(token_score, full_score), s))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored or scored[0][0] < threshold:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        return None  # ambiguous
    return scored[0][1]
