from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_engine, init_db
from app.models import Merchant
from app.routers import cash, core, demo, sales, suppliers, udhaar


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with Session(get_engine()) as s:
        empty = s.exec(select(Merchant)).first() is None
    if empty:
        from app.services.demo import reset_demo

        reset_demo()
    yield


settings = get_settings()
app = FastAPI(title="Vyapar Hub API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (core.router, sales.router, cash.router, suppliers.router, udhaar.router, demo.router):
    app.include_router(r)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
