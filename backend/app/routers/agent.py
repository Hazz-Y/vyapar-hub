from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import clock
from app.agent.runner import run_agent
from app.agent.tools import ToolContext
from app.deps import MerchantId, SessionDep, get_merchant

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list)


def make_context(session, merchant_id: int) -> ToolContext:
    m = get_merchant(session, merchant_id)
    return ToolContext(session=session, merchant=m, now=clock.now(), today=clock.today(),
                       demo_start=clock.demo_start())


@router.post("/chat")
def chat(body: ChatRequest, session: SessionDep, merchant_id: MerchantId = 1) -> dict:
    ctx = make_context(session, merchant_id)
    return run_agent(ctx, body.message, [h.model_dump() for h in body.history])
