"""Customer-facing message templates (reminders and win-back offers), by customer language."""
from datetime import date

from app.services.fmt import fmt_date, rupees


def reminder_text(lang: str, customer_first: str, shop: str, amount: int, due: date, link: str) -> str:
    amt, when = rupees(amount), fmt_date(due)
    if lang == "ta":
        return (f"வணக்கம் {customer_first}! {shop}-இல் உங்கள் {amt} நிலுவை {when} அன்று செலுத்த வேண்டும். "
                f"இங்கே செலுத்தலாம்: {link}")
    if lang == "en":
        return f"Hello {customer_first}, a friendly reminder from {shop}: {amt} is due on {when}. Pay here: {link}"
    return (f"Namaste {customer_first} ji! {shop} se yaad dilana tha: aapka {amt} ka udhaar {when} tak dena tha. "
            f"Yahan se UPI se de sakte hain: {link} Dhanyavaad!")


def winback_text(lang: str, customer_first: str, shop: str, discount_pct: int) -> str:
    if lang == "ta":
        return (f"வணக்கம் {customer_first}! உங்களை {shop}-இல் பார்க்கவில்லை. இந்த வாரம் வந்தால் "
                f"{discount_pct}% தள்ளுபடி. நன்றி!")
    if lang == "en":
        return f"Hello {customer_first}, we miss you at {shop}! Get {discount_pct}% off on your next visit this week."
    return (f"Namaste {customer_first} ji! Kaafi din se {shop} nahi aaye. Is hafte aaiye, aapke liye "
            f"{discount_pct}% ki chhoot hai. Dhanyavaad!")
