from datetime import date

from fastapi import APIRouter, Query

from app import clock
from app.deps import MerchantId, SessionDep, get_merchant
from app.services.forecast import backtest, cash_radar

router = APIRouter(prefix="/cash", tags=["cash"])


@router.get("/radar")
def radar(session: SessionDep, merchant_id: MerchantId = 1,
          move_payable_id: int | None = Query(None, description="What-if: payable to move"),
          move_to: date | None = Query(None, description="What-if: new due date")) -> dict:
    m = get_merchant(session, merchant_id)
    moves = {move_payable_id: move_to} if move_payable_id and move_to else None
    return cash_radar(session, m, clock.today(), clock.now(), clock.demo_start(), moves)


@router.get("/backtest")
def get_backtest(session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    get_merchant(session, merchant_id)
    return backtest(session, merchant_id, clock.today())
