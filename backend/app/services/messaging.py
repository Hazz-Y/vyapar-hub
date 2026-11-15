"""Customer messages and Soundbox announcements.

WhatsApp sending is not enabled in this build: every customer message is rendered as an
on-screen preview and written to MessageLog (channel="preview"). Nothing leaves the app.
"""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import MessageLog, SoundboxEvent


def send_message(session: Session, merchant_id: int, to: str, body: str, kind: str, now: datetime,
                 commit: bool = True) -> MessageLog:
    log = MessageLog(merchant_id=merchant_id, channel="preview", to=to, body=body, status="preview",
                     created_at=now, kind=kind, detail="Shown as an on-screen preview (WhatsApp not enabled).")
    session.add(log)
    if commit:
        session.commit()
        session.refresh(log)
    return log


def announce(session: Session, merchant_id: int, kind: str, text: str, now: datetime) -> SoundboxEvent:
    ev = SoundboxEvent(merchant_id=merchant_id, kind=kind, text=text, created_at=now)
    session.add(ev)
    session.commit()
    session.refresh(ev)
    try:
        from app.services.hardware import display_from_speech
        display_from_speech(text)
    except Exception:
        pass
    return ev


def soundbox_events(session: Session, merchant_id: int, after_id: int = 0, limit: int = 20) -> list[SoundboxEvent]:
    return list(session.exec(select(SoundboxEvent).where(SoundboxEvent.merchant_id == merchant_id,
                                                         SoundboxEvent.id > after_id)
                             .order_by(SoundboxEvent.id).limit(limit)).all())
