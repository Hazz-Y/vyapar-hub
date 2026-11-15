"""Live smoke test for LLM tool calling (Groq or xAI). Usage: python scripts/smoke_llm.py

Needs GROQ_API_KEY (or XAI_API_KEY) in backend/.env. Runs against a throwaway seeded database, so the real
demo DB is untouched.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()).as_posix()}/smoke.db"

from sqlmodel import Session  # noqa: E402

from app import clock  # noqa: E402
from app.agent.runner import client_from_settings, run_agent  # noqa: E402
from app.agent.tools import ToolContext  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.models import Merchant  # noqa: E402
from app.services.demo import reset_demo  # noqa: E402

PHRASES = [
    ("Agarwal ka payment 7 tareekh ko kar do", "reschedule_payable"),
    ("Sunita ji ne 650 ka udhaar liya, Friday tak denge", "log_udhaar"),
]


def main() -> int:
    s = get_settings()
    if s.llm_mode == "fallback":
        print("No GROQ_API_KEY or XAI_API_KEY in backend/.env - add one to run this smoke test.")
        return 1
    import openai

    print(f"openai SDK {openai.__version__}, provider {s.llm_mode}, model {s.llm_model}")
    reset_demo()
    ok = True
    for text, expected_kind in PHRASES:
        with Session(get_engine()) as session:
            ctx = ToolContext(session=session, merchant=session.get(Merchant, 1), now=clock.now(),
                              today=clock.today(), demo_start=clock.demo_start())
            t0 = time.perf_counter()
            r = run_agent(ctx, text)
            dt = time.perf_counter() - t0
        kinds = [a["kind"] for a in r["pending_actions"]]
        passed = r["mode"] == s.llm_mode and expected_kind in kinds
        ok &= passed
        print(f"\n[{'PASS' if passed else 'FAIL'}] {text}  ({dt:.1f}s, mode={r['mode']})")
        for t in r["tool_trace"]:
            print(f"   tool {t['tool']} args={t['args']}")
        print(f"   reply: {r['reply_text']}")
        print(f"   pending: {kinds}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
