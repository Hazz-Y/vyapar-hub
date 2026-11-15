"""Subah ki Report: assembled only from tool outputs. Every number comes from a service."""
from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Session

from app.models import Merchant
from app.services.fmt import rupees
from app.services.forecast import cash_radar
from app.services.insights import growth_insights
from app.services.sales import sales_summary
from app.services.udhaar import udhaar_totals


def build_briefing(session: Session, merchant: Merchant, today: date, now: datetime, demo_start: date) -> dict:
    sales = sales_summary(session, merchant.id, today)
    radar = cash_radar(session, merchant, today, now, demo_start)
    udhaar = udhaar_totals(session, merchant.id, today)
    growth = growth_insights(session, merchant.id, today)

    y, pct = sales["yesterday"]["total"], sales["yesterday_vs_usual_pct"]
    if pct is None:
        sales_line = f"Kal {rupees(y)} ki bikri hui."
    else:
        word = "zyada" if pct >= 0 else "kam"
        sales_line = f"Kal {rupees(y)} ki bikri hui, aam {sales['yesterday_weekday']} se {abs(pct)}% {word}."

    today_dues = radar["days"][0]["payables"]
    due_total = sum(p["amount"] for p in today_dues)
    if today_dues:
        names = ", ".join(p["supplier"] for p in today_dues[:3])
        verb = "hai" if len(today_dues) == 1 else "hain"
        pay_line = f"Aaj {len(today_dues)} payment due {verb}, kul {rupees(due_total)}: {names}."
    else:
        pay_line = "Aaj koi supplier payment due nahi hai."

    if udhaar["due_today_or_overdue_count"]:
        names = ", ".join(x["name"] for x in udhaar["due_today_or_overdue"][:3])
        udhaar_line = (f"Aaj {udhaar['due_today_or_overdue_count']} logon se {rupees(udhaar['due_today_or_overdue_total'])} "
                       f"udhaar lena hai: {names}.")
    else:
        udhaar_line = f"Kul khula udhaar {rupees(udhaar['open_total'])} hai."

    if radar["shortfalls"]:
        sf = radar["shortfalls"][0]
        suggestion = f"Dhyan dein: {sf['date_text']} ko paisa kam pad sakta hai."
        if sf["fix"]:
            suggestion += " " + sf["fix"]["text"]
        suggestion_kind = "cash"
    elif growth["lapsed_regulars"]["count"]:
        suggestion = (f"{growth['lapsed_regulars']['count']} regular grahak 3 hafte se nahi aaye. "
                      f"Unhe offer bhejein?")
        suggestion_kind = "growth"
    else:
        suggestion = growth["summary_text"].split(".")[0] + "."
        suggestion_kind = "growth"

    greeting = f"Namaste {merchant.owner_name.split()[0]} ji, Subah ki Report."
    spoken = " ".join([greeting, sales_line, pay_line, udhaar_line, suggestion])
    return {
        "date": today.isoformat(), "spoken_text": spoken,
        "cards": [
            {"kind": "sales", "title": "Kal ki bikri", "value": rupees(y), "detail": sales_line,
             "vs_usual_pct": pct},
            {"kind": "payments", "title": "Aaj ke payment", "value": rupees(due_total), "detail": pay_line,
             "count": len(today_dues)},
            {"kind": "udhaar", "title": "Udhaar vasooli", "value": rupees(udhaar["due_today_or_overdue_total"]),
             "detail": udhaar_line, "count": udhaar["due_today_or_overdue_count"]},
        ],
        "suggestion": {"kind": suggestion_kind, "text": suggestion},
    }
