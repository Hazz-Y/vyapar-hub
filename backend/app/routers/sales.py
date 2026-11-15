from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Query
from sqlmodel import select

from app import clock
from app.deps import MerchantId, SessionDep, get_merchant
from app.models import Transaction
from app.services.sales import daily_inflows, sales_summary

router = APIRouter(tags=["sales"])


@router.get("/sales/summary")
def summary(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    get_merchant(session, merchant_id)
    return sales_summary(session, merchant_id, clock.today())


@router.get("/sales/daily")
def daily(session: SessionDep, merchant_id: MerchantId = 1, days: int = Query(30, ge=1, le=400)) -> list[dict]:
    today = clock.today()
    data = daily_inflows(session, merchant_id, today - timedelta(days=days), today + timedelta(days=1))
    return [{"date": d.isoformat(), "total": v} for d, v in data.items()]


@router.get("/transactions")
def transactions(session: SessionDep, merchant_id: MerchantId = 1, limit: int = Query(50, le=500),
                 direction: Literal["in", "out"] | None = None, source: str | None = None) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.merchant_id == merchant_id)
    if direction:
        stmt = stmt.where(Transaction.direction == direction)
    if source:
        stmt = stmt.where(Transaction.source == source)
    return list(session.exec(stmt.order_by(Transaction.ts.desc(), Transaction.id.desc()).limit(limit)).all())
