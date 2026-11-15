"""Tests run against a temporary SQLite DB seeded for a fixed demo date."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="vyapar-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["DEMO_DATE"] = "2026-11-15"
os.environ["DEMO_NOW"] = ""
os.environ["ENABLE_SCHEDULER"] = "false"
# Force offline fallbacks in tests regardless of backend/.env.
for key in ("GROQ_API_KEY", "XAI_API_KEY", "SARVAM_API_KEY"):
    os.environ[key] = ""

import shutil  # noqa: E402
from datetime import datetime  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import clock  # noqa: E402
from app.db import get_engine, reset_engine  # noqa: E402
from app.seed import DEMO_START_TIME  # noqa: E402
from app.services.demo import demo_date, reset_demo  # noqa: E402

DEMO_DATE = "2026-11-15"
_DB = _tmp / "test.db"
_TEMPLATE = _tmp / "template.db"


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    result = reset_demo()
    with get_engine().connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    reset_engine()
    shutil.copyfile(_DB, _TEMPLATE)
    return result


@pytest.fixture
def fresh_db():
    """Restore the freshly seeded state (fast copy of the seeded DB) for tests that mutate it."""
    reset_engine()
    for suffix in ("-wal", "-shm"):
        (_tmp / f"test.db{suffix}").unlink(missing_ok=True)
    shutil.copyfile(_TEMPLATE, _DB)
    clock.set_now(datetime.combine(demo_date(), DEMO_START_TIME))
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
