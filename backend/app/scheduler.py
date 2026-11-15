"""Background jobs on the demo clock (APScheduler).

tick() is idempotent and runs every 30 s; "jump to Friday" calls it directly after moving the clock.
* Udhaar reminders: on the due date at 10:00 local time (or later if overdue), once per entry.
  Auto mode -> sent at once (preview); suggest mode -> a pending action for the merchant to approve.
* Subah ki Report: once a day at the shop's opening time, announced on the Soundbox.
"""
from __future__ import annotations

import logging
from datetime import datetime, time

from sqlmodel import Session, select

from app import clock
from app.db import get_engine
from app.models import AppState, Customer, Merchant, PendingAction, Udhaar

log = logging.getLogger("vyapar.scheduler")
REMINDER_TIME = time(10, 0)
_scheduler = None


def _reminder_due(u: Udhaar, now: datetime) -> bool:
    return u.status == "open" and (u.due_date < now.date() or (u.due_date == now.date() and now.time() >= REMINDER_TIME))


def _already_drafted(session: Session, udhaar_id: int) -> bool:
    rows = session.exec(select(PendingAction).where(PendingAction.kind == "send_reminder",
                                                    PendingAction.status.in_(("pending", "executed")))).all()
    return any(r.payload.get("udhaar_id") == udhaar_id for r in rows)


def run_due_reminders(session: Session, merchant: Merchant, now: datetime) -> list[dict]:
    from app.agent.tools import DraftReminderIn, ToolContext, draft_udhaar_reminder

    out = []
    rows = session.exec(select(Udhaar, Customer).join(Customer).where(
        Udhaar.merchant_id == merchant.id, Udhaar.status == "open", Udhaar.due_date <= now.date())).all()
    for u, c in rows:
        if not _reminder_due(u, now) or not c.phone or _already_drafted(session, u.id):
            continue
        ctx = ToolContext(session=session, merchant=merchant, now=now, today=now.date(),
                          demo_start=clock.demo_start())
        r = draft_udhaar_reminder(ctx, DraftReminderIn(udhaar_id=u.id))
        out.append({"udhaar_id": u.id, "customer": c.name, "auto_sent": bool(r.get("auto_executed")),
                    "pending_action_id": r.get("pending_action_id")})
    return out


def run_morning_briefing(session: Session, merchant: Merchant, now: datetime) -> dict | None:
    from app.services.briefing import build_briefing
    from app.services.messaging import announce

    h, m = map(int, merchant.opening_time.split(":"))
    if now.time() < time(h, m):
        return None
    key = f"briefing_sent:{merchant.id}"
    row = session.get(AppState, key)
    if row and row.value == now.date().isoformat():
        return None
    b = build_briefing(session, merchant, now.date(), now, clock.demo_start())
    announce(session, merchant.id, "briefing", b["spoken_text"], now)
    row = row or AppState(key=key, value="")
    row.value = now.date().isoformat()
    session.add(row)
    session.commit()
    return b


def tick(now: datetime | None = None) -> dict:
    now = now or clock.now()
    result = {"now": now.isoformat(), "reminders": [], "briefings": []}
    with Session(get_engine()) as session:
        for merchant in session.exec(select(Merchant)).all():
            result["reminders"] += run_due_reminders(session, merchant, now)
            if run_morning_briefing(session, merchant, now):
                result["briefings"].append(merchant.id)
    return result


def _safe_tick() -> None:
    try:
        tick()
    except Exception:  # never let a job crash the scheduler thread
        log.exception("scheduler tick failed")


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_safe_tick, "interval", seconds=30, id="tick", max_instances=1, coalesce=True)
    _scheduler.start()


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
