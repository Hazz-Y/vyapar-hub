"""UPI deep links (upi://pay). No money moves: the customer's own UPI app handles payment."""
from urllib.parse import quote


def upi_pay_link(vpa: str, payee_name: str, amount: int, note: str) -> str:
    fields = [("pa", vpa), ("pn", payee_name), ("am", f"{amount:.2f}"), ("cu", "INR"), ("tn", note)]
    return "upi://pay?" + "&".join(f"{k}={quote(str(v), safe='')}" for k, v in fields)
