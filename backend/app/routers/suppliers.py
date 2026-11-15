from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import clock
from app.agent.tools import DraftPaymentIn, DraftRescheduleIn, draft_reschedule_payable, draft_supplier_payment
from app.deps import MerchantId, SessionDep, get_merchant
from app.models import Payable, Supplier
from app.routers.agent import make_context
from app.services.actions import action_out
from app.services.gst import gst_csv, gst_rows, month_range
from app.services.matching import match_ledger

router = APIRouter(tags=["suppliers"])
UPCOMING = ("scheduled", "rescheduled")


@router.get("/suppliers")
def suppliers(session: SessionDep, merchant_id: MerchantId = 1) -> list[Supplier]:
    return list(session.exec(select(Supplier).where(Supplier.merchant_id == merchant_id)
                             .order_by(Supplier.id)).all())


def payable_rows(session: Session, merchant_id: int, status: str | None = "upcoming",
                 limit: int = 100) -> list[dict]:
    stmt = select(Payable, Supplier).join(Supplier).where(Payable.merchant_id == merchant_id)
    if status == "upcoming":
        stmt = stmt.where(Payable.status.in_(UPCOMING))
    elif status:
        stmt = stmt.where(Payable.status == status)
    order = Payable.due_date if status in ("upcoming", *UPCOMING) else Payable.due_date.desc()
    rows = session.exec(stmt.order_by(order, Payable.id).limit(limit)).all()
    today = clock.today()
    return [{"id": p.id, "supplier_id": s.id, "supplier": s.name, "amount": p.amount,
             "due_date": p.due_date.isoformat(), "days_to_due": (p.due_date - today).days,
             "status": p.status, "invoice_no": p.invoice_no,
             "original_due_date": p.original_due_date.isoformat() if p.original_due_date else None}
            for p, s in rows]


@router.get("/payables")
def payables(session: SessionDep, merchant_id: MerchantId = 1,
             status: Literal["upcoming", "scheduled", "paid", "rescheduled"] | None = "upcoming",
             limit: int = 100) -> list[dict]:
    return payable_rows(session, merchant_id, status, limit)


def _payable(session: Session, payable_id: int, merchant_id: int) -> tuple[Payable, Supplier]:
    p = session.get(Payable, payable_id)
    if p is None or p.merchant_id != merchant_id:
        raise HTTPException(404, "Payable not found")
    return p, session.get(Supplier, p.supplier_id)


@router.post("/payables/{payable_id}/pay/draft")
def draft_pay(payable_id: int, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    p, s = _payable(session, payable_id, merchant_id)
    ctx = make_context(session, merchant_id)
    r = draft_supplier_payment(ctx, DraftPaymentIn(supplier_name=s.name, amount=p.amount))
    return {**r, "pending_actions": [action_out(a) for a in ctx.actions]}


class RescheduleDraft(BaseModel):
    new_date: date | None = Field(None, description="Leave empty to use Cash Radar's suggested safe date")


@router.post("/payables/{payable_id}/reschedule/draft")
def draft_reschedule(payable_id: int, body: RescheduleDraft, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    _payable(session, payable_id, merchant_id)
    ctx = make_context(session, merchant_id)
    args = DraftRescheduleIn(payable_id=payable_id, when=body.new_date.isoformat() if body.new_date else None,
                             use_suggested_date=body.new_date is None)
    r = draft_reschedule_payable(ctx, args)
    if "error" in r:
        raise HTTPException(422, r["speak"])
    return {**r, "pending_actions": [action_out(a) for a in ctx.actions]}


@router.get("/suppliers/matching")
def matching(session: SessionDep, merchant_id: MerchantId = 1, limit: int = Query(300, le=5000)) -> dict:
    get_merchant(session, merchant_id)
    return match_ledger(session, merchant_id, limit)


@router.get("/suppliers/gst-export.csv", response_class=PlainTextResponse)
def gst_export(session: SessionDep, merchant_id: MerchantId = 1,
               month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$")) -> PlainTextResponse:
    m = get_merchant(session, merchant_id)
    start, end = month_range(month, clock.today())
    body = gst_csv(gst_rows(session, m, start, end))
    filename = f"gst-purchases-{m.upi_vpa.split('@')[0]}-{start:%Y-%m}.csv"
    return PlainTextResponse(body, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
