from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from app import clock
from app.config import get_settings
from app.deps import MerchantId, SessionDep, get_merchant
from app.models import Customer, Merchant, MessageLog, Settings

router = APIRouter(tags=["core"])


@router.get("/status")
def status() -> dict:
    s = get_settings()
    return {"llm": s.llm_mode, "llm_model": s.llm_model, "voice": s.voice_mode, "messaging": s.messaging_mode,
            "now": clock.now().isoformat(), "demo_date": clock.demo_start().isoformat(),
            "synthetic_data": True}


@router.get("/merchants")
def merchants(session: SessionDep) -> list[Merchant]:
    return list(session.exec(select(Merchant)).all())


@router.get("/merchants/{merchant_id}")
def merchant(merchant_id: int, session: SessionDep) -> Merchant:
    return get_merchant(session, merchant_id)


@router.get("/customers")
def customers(session: SessionDep, merchant_id: MerchantId = 1, limit: int = 100, offset: int = 0) -> list[dict]:
    rows = session.exec(select(Customer).where(Customer.merchant_id == merchant_id)
                        .order_by(Customer.id).offset(offset).limit(limit)).all()
    return [{"id": c.id, "name": c.name, "phone": c.phone, "opted_in": c.opted_in,
             "language": c.language, "payer_hash": c.payer_hash} for c in rows]


Autonomy = Literal["suggest", "auto"]


class SettingsUpdate(BaseModel):
    autonomy_udhaar: Autonomy | None = None
    autonomy_growth: Autonomy | None = None
    autonomy_supplier: Autonomy | None = None
    autonomy_cash: Autonomy | None = None
    language: Literal["hi", "en", "ta", "hinglish"] | None = None


@router.get("/settings")
def get_settings_row(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    row = session.get(Settings, merchant_id) or Settings(merchant_id=merchant_id)
    return _settings_out(row)


@router.put("/settings")
def update_settings(body: SettingsUpdate, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    get_merchant(session, merchant_id)
    row = session.get(Settings, merchant_id) or Settings(merchant_id=merchant_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _settings_out(row)


def _settings_out(row: Settings) -> dict:
    d = row.model_dump()
    d["note"] = "Supplier payments and reschedules always need approval, whatever the setting."
    return d


@router.get("/messages")
def messages(session: SessionDep, merchant_id: MerchantId = 1, limit: int = 50) -> list[MessageLog]:
    return list(session.exec(select(MessageLog).where(MessageLog.merchant_id == merchant_id)
                             .order_by(MessageLog.id.desc()).limit(limit)).all())
