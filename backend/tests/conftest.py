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
for key in ("XAI_API_KEY", "SARVAM_API_KEY", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
            "DEMO_CUSTOMER_PHONE"):
    os.environ[key] = ""

import pytest  # noqa: E402

from app.services.demo import reset_demo  # noqa: E402

DEMO_DATE = "2026-11-15"


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    return reset_demo()


@pytest.fixture
def fresh_db():
    """Re-seed for tests that mutate state."""
    return reset_demo()
