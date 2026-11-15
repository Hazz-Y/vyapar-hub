from typing import Literal

from fastapi import APIRouter
from sqlmodel import Session, select

from app import clock
from app.deps import MerchantId, SessionDep
from app.models import Payable, Supplier

router = APIRouter(tags=["suppliers"])


@router.get("/suppliers")
def suppliers(session: SessionDep, merchant_id: MerchantId = 1) -> list[Supplier]:
    return list(session.exec(select(Supplier).where(Supplier.merchant_id == merchant_id)
                             .order_by(Supplier.id)).all())


def payable_rows(session: Session, merchant_id: int, status: str | None = "scheduled",
                 limit: int = 100) -> list[dict]:
    stmt = select(Payable, Supplier).join(Supplier).where(Payable.merchant_id == merchant_id)
    if status:
        stmt = stmt.where(Payable.status == status)
    order = Payable.due_date if status in ("scheduled", "rescheduled") else Payable.due_date.desc()
    rows = session.exec(stmt.order_by(order, Payable.id).limit(limit)).all()
    today = clock.today()
    return [{"id": p.id, "supplier_id": s.id, "supplier": s.name, "amount": p.amount,
             "due_date": p.due_date.isoformat(), "days_to_due": (p.due_date - today).days,
             "status": p.status, "invoice_no": p.invoice_no,
             "original_due_date": p.original_due_date.isoformat() if p.original_due_date else None}
            for p, s in rows]


@router.get("/payables")
def payables(session: SessionDep, merchant_id: MerchantId = 1,
             status: Literal["scheduled", "paid", "rescheduled"] | None = "scheduled",
             limit: int = 100) -> list[dict]:
    return payable_rows(session, merchant_id, status, limit)
