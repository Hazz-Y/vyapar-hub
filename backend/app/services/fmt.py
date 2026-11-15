"""Ready-to-speak formatting for money and dates (Indian digit grouping)."""
from datetime import date


def rupees(v: int | float) -> str:
    n = int(round(v))
    digits = str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return ("-₹" if n < 0 else "₹") + digits


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b')} ({d.strftime('%A')})"
