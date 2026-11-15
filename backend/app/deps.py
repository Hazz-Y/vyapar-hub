from typing import Annotated

from fastapi import Depends, HTTPException, Query
from sqlmodel import Session

from app.db import get_session
from app.models import Merchant

SessionDep = Annotated[Session, Depends(get_session)]
MerchantId = Annotated[int, Query(ge=1, description="Merchant id (1 = Ramesh Kirana Store)")]


def get_merchant(session: Session, merchant_id: int) -> Merchant:
    m = session.get(Merchant, merchant_id)
    if m is None:
        raise HTTPException(404, f"merchant {merchant_id} not found")
    return m
