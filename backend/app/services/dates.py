"""Resolve spoken Hindi / Hinglish / English date phrases to dates (server-side, never by the LLM)."""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

WEEKDAYS = {
    0: ["monday", "mon", "somvar", "somwar", "सोमवार"],
    1: ["tuesday", "tue", "mangalvar", "mangalwar", "mangal", "मंगलवार"],
    2: ["wednesday", "wed", "budhvar", "budhwar", "budh", "बुधवार"],
    3: ["thursday", "thu", "guruvar", "guruwar", "veervar", "brihaspativar", "गुरुवार", "बृहस्पतिवार"],
    4: ["friday", "fri", "shukravar", "shukrawar", "shukra", "शुक्रवार", "फ्राइडे"],
    5: ["saturday", "sat", "shanivar", "shaniwar", "shani", "शनिवार"],
    6: ["sunday", "sun", "ravivar", "raviwar", "itvaar", "itwar", "रविवार", "इतवार"],
}
WEEKDAY_LOOKUP = {name: wd for wd, names in WEEKDAYS.items() for name in names}


def weekday_index(word: str) -> int | None:
    return WEEKDAY_LOOKUP.get(word.strip().lower())


def next_weekday(today: date, weekday: int) -> date:
    """'Friday tak' = the coming Friday, strictly after today."""
    ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=ahead or 7)


def next_day_of_month(today: date, day: int) -> date:
    """'7 tareekh' = the next 7th strictly after today (clamped to month length)."""
    if not 1 <= day <= 31:
        raise ValueError("day of month must be 1-31")
    y, m = today.year, today.month
    for _ in range(3):
        d = date(y, m, min(day, calendar.monthrange(y, m)[1]))
        if d > today:
            return d
        m += 1
        if m > 12:
            y, m = y + 1, 1
    raise ValueError("could not resolve date")


def resolve_phrase(today: date, phrase: str) -> date | None:
    p = phrase.strip().lower()
    if not p:
        return None
    try:
        return date.fromisoformat(p)
    except ValueError:
        pass
    if p in ("aaj", "today", "आज"):
        return today
    if p in ("kal", "tomorrow", "कल"):
        return today + timedelta(days=1)
    if p in ("parson", "parso", "परसों"):
        return today + timedelta(days=2)
    if p in ("agle hafte", "next week", "agle week", "अगले हफ्ते"):
        return today + timedelta(days=7)
    m = re.fullmatch(r"(\d{1,2})\s*(tareekh|tarikh|tarik|तारीख|th|st|nd|rd)?", p)
    if m:
        return next_day_of_month(today, int(m.group(1)))
    m = re.fullmatch(r"(\d{1,2})\s*(din|days?|दिन)(\s*(mein|me|baad|में|बाद))?", p)
    if m:
        return today + timedelta(days=int(m.group(1)))
    wd = weekday_index(p)
    if wd is not None:
        return next_weekday(today, wd)
    return None
