"""Agent tools. Each tool is a plain function with a Pydantic input model.

Rules enforced here (not in the LLM):
* every number is computed by a service and returned ready to speak (`speak` field);
* draft_* / log_udhaar only create a PendingAction with a read-back. Nothing executes until
  POST /actions/{id}/approve is called with the PIN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.models import Customer, Merchant, Payable, PendingAction, Supplier, Udhaar
from app.services.actions import action_out, create_pending
from app.services.briefing import build_briefing
from app.services.customers import display_name, find_customer
from app.services.dates import next_day_of_month, resolve_phrase
from app.services.fmt import fmt_date, rupees
from app.services.forecast import HORIZON, cash_radar
from app.services.insights import growth_insights, lapsed_regulars
from app.services.messages import reminder_text, winback_text
from app.services.sales import sales_summary
from app.services.suppliers import find_supplier
from app.services.udhaar import OPEN_STATUSES, list_udhaar, udhaar_totals
from app.services.upi import upi_pay_link


@dataclass
class ToolContext:
    session: Session
    merchant: Merchant
    now: datetime
    today: date
    demo_start: date
    actions: list[PendingAction] = field(default_factory=list)

    def radar(self, moves: dict[int, date] | None = None) -> dict:
        return cash_radar(self.session, self.merchant, self.today, self.now, self.demo_start, moves)

    def draft(self, agent: str, kind: str, payload: dict, readback: str) -> dict:
        pa = create_pending(self.session, self.merchant.id, agent, kind, payload, readback, self.now)
        self.actions.append(pa)
        return action_out(pa)

    def auto_execute_last(self) -> dict | None:
        """If the merchant set this agent to auto (messages only), the executor runs it now."""
        from app.services.executor import auto_approve

        return auto_approve(self.session, self.actions[-1], self.now)


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable[[ToolContext, Any], dict]

    def schema(self) -> dict:
        params = self.input_model.model_json_schema()
        params.pop("title", None)
        for prop in params.get("properties", {}).values():
            prop.pop("title", None)
        params.setdefault("properties", {})
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": params}}

    def run(self, ctx: ToolContext, raw_args: dict) -> dict:
        args = self.input_model.model_validate(raw_args or {})
        return self.fn(ctx, args)


class NoArgs(BaseModel):
    pass


# ---------------------------------------------------------------- read tools


def get_sales_summary(ctx: ToolContext, _: NoArgs) -> dict:
    s = sales_summary(ctx.session, ctx.merchant.id, ctx.today)
    y, pct = s["yesterday"]["total"], s["yesterday_vs_usual_pct"]
    speak = f"Kal {rupees(y)} ki bikri hui"
    if pct is not None:
        speak += f", aam {s['yesterday_weekday']} se {abs(pct)}% {'zyada' if pct >= 0 else 'kam'}"
    speak += f". Aaj ab tak {rupees(s['today']['total'])}."
    return {"speak": speak, "yesterday_total": rupees(y), "yesterday_vs_usual_pct": pct,
            "usual_for_yesterday": rupees(s["usual_for_yesterday"]), "today_so_far": rupees(s["today"]["total"]),
            "today_txn_count": s["today"]["count"]}


def get_cash_radar(ctx: ToolContext, _: NoArgs) -> dict:
    r = ctx.radar()
    return {"speak": r["summary_text"], "balance_now": rupees(r["balance_now"]), "buffer": rupees(r["buffer"]),
            "flagged_days": r["flagged_days"],
            "shortfalls": [{"date": s["date_text"], "days_ahead": s["days_ahead"],
                            "lowest_balance": rupees(s["lowest_balance_p10"]), "gap": rupees(s["gap"]),
                            "cause": s["cause"] and {"payable_id": s["cause"]["payable_id"],
                                                     "supplier": s["cause"]["supplier"],
                                                     "amount": rupees(s["cause"]["amount"])},
                            "suggested_date": s["fix"] and s["fix"]["move_to_text"]} for s in r["shortfalls"]]}


class ListPayablesIn(BaseModel):
    days_ahead: int = Field(14, ge=0, le=60, description="Look this many days ahead")
    supplier_name: str | None = Field(None, description="Optional supplier name as spoken, e.g. 'Agarwal'")


def list_payables(ctx: ToolContext, a: ListPayablesIn) -> dict:
    stmt = select(Payable, Supplier).join(Supplier).where(
        Payable.merchant_id == ctx.merchant.id, Payable.status.in_(("scheduled", "rescheduled")),
        Payable.due_date <= ctx.today + timedelta(days=a.days_ahead))
    if a.supplier_name:
        sup = find_supplier(ctx.session, ctx.merchant.id, a.supplier_name)
        if sup is None:
            return _supplier_not_found(ctx, a.supplier_name)
        stmt = stmt.where(Payable.supplier_id == sup.id)
    rows = ctx.session.exec(stmt.order_by(Payable.due_date, Payable.id)).all()
    items = [{"payable_id": p.id, "supplier": s.name, "amount": rupees(p.amount), "due": fmt_date(p.due_date)}
             for p, s in rows]
    total = sum(p.amount for p, _ in rows)
    return {"speak": f"Agle {a.days_ahead} din mein {len(items)} payment due hain, kul {rupees(total)}.",
            "count": len(items), "total": rupees(total), "payables": items[:15]}


class ListUdhaarIn(BaseModel):
    status: str = Field("open", description="open, settled or all")


def list_udhaar_tool(ctx: ToolContext, a: ListUdhaarIn) -> dict:
    rows = list_udhaar(ctx.session, ctx.merchant.id, ctx.today, None if a.status == "all" else a.status)
    t = udhaar_totals(ctx.session, ctx.merchant.id, ctx.today)
    speak = f"{t['open_count']} logon ka kul {rupees(t['open_total'])} udhaar khula hai."
    if t["due_today_or_overdue_count"]:
        speak += f" Aaj tak {t['due_today_or_overdue_count']} se {rupees(t['due_today_or_overdue_total'])} lena hai."
    return {"speak": speak, "open_count": t["open_count"], "open_total": rupees(t["open_total"]),
            "entries": [{"udhaar_id": r["id"], "name": r["display_name"], "amount": rupees(r["amount"]),
                         "due": fmt_date(date.fromisoformat(r["due_date"])), "status": r["status"]}
                        for r in rows[:12]]}


def get_growth_insights(ctx: ToolContext, _: NoArgs) -> dict:
    g = growth_insights(ctx.session, ctx.merchant.id, ctx.today)
    fest = g["festival"]
    return {"speak": g["summary_text"], "peak_hour": g["peak_hours"]["peak_hour_label"],
            "slowest_day": g["slow_days"]["slowest"]["weekday_name"],
            "slowest_day_below_avg_pct": g["slow_days"]["slowest"]["below_avg_pct"],
            "festival": fest and {"name": fest["festival"], "this_year": rupees(fest["this_year"]["total"]),
                                  "last_year": rupees(fest["last_year"]["total"]), "change_pct": fest["change_pct"]},
            "lapsed_regulars": g["lapsed_regulars"]["count"],
            "lapsed_opted_in": g["lapsed_regulars"]["opted_in_count"]}


def get_morning_briefing(ctx: ToolContext, _: NoArgs) -> dict:
    b = build_briefing(ctx.session, ctx.merchant, ctx.today, ctx.now, ctx.demo_start)
    return {"speak": b["spoken_text"], "cards": [{"title": c["title"], "value": c["value"]} for c in b["cards"]],
            "suggestion": b["suggestion"]["text"]}


# ---------------------------------------------------------------- draft tools


def _supplier_not_found(ctx: ToolContext, spoken: str) -> dict:
    names = [s.name for s in ctx.session.exec(select(Supplier).where(Supplier.merchant_id == ctx.merchant.id))]
    return {"error": "supplier_not_found", "speak": f"'{spoken}' naam ka supplier nahi mila. Kaun sa supplier?",
            "suppliers": names}


class DraftPaymentIn(BaseModel):
    supplier_name: str = Field(description="Supplier as spoken, e.g. 'Sharma ji'")
    amount: int = Field(gt=0, le=500_000, description="Amount in rupees exactly as the merchant said")


def draft_supplier_payment(ctx: ToolContext, a: DraftPaymentIn) -> dict:
    sup = find_supplier(ctx.session, ctx.merchant.id, a.supplier_name)
    if sup is None:
        return _supplier_not_found(ctx, a.supplier_name)
    linked = ctx.session.exec(select(Payable).where(
        Payable.supplier_id == sup.id, Payable.status.in_(("scheduled", "rescheduled")),
        Payable.amount == a.amount).order_by(Payable.due_date)).first()
    balance = ctx.radar()["balance_now"]
    readback = f"{rupees(a.amount)} {sup.name} ko bhejna hai, UPI {sup.upi_vpa}. Sahi hai?"
    action = ctx.draft("supplier", "pay_supplier", {
        "supplier_id": sup.id, "supplier": sup.name, "recipient": sup.name, "upi_vpa": sup.upi_vpa,
        "amount": a.amount, "payable_id": linked.id if linked else None}, readback)
    return {"speak": readback, "pending_action_id": action["id"], "needs_approval": True,
            "balance_after": rupees(balance - a.amount)}


class DraftRescheduleIn(BaseModel):
    supplier_name: str | None = Field(None, description="Supplier as spoken, e.g. 'Agarwal'")
    payable_id: int | None = Field(None, description="Payable id if known from another tool")
    day_of_month: int | None = Field(None, ge=1, le=31, description="For '7 tareekh' pass 7")
    when: str | None = Field(None, description="Spoken date phrase: 'Friday', 'kal', '10 din baad', or ISO date")
    use_suggested_date: bool = Field(False, description="Use Cash Radar's suggested safe date")


def _pick_payable(ctx: ToolContext, a: DraftRescheduleIn) -> tuple[Payable | None, Supplier | None, dict | None]:
    if a.payable_id:
        p = ctx.session.get(Payable, a.payable_id)
        if p is None or p.merchant_id != ctx.merchant.id:
            return None, None, {"error": "payable_not_found", "speak": "Yeh payment nahi mila."}
        return p, ctx.session.get(Supplier, p.supplier_id), None
    if not a.supplier_name:
        return None, None, {"error": "need_supplier", "speak": "Kis supplier ka payment aage karna hai?"}
    sup = find_supplier(ctx.session, ctx.merchant.id, a.supplier_name)
    if sup is None:
        return None, None, _supplier_not_found(ctx, a.supplier_name)
    p = ctx.session.exec(select(Payable).where(
        Payable.supplier_id == sup.id, Payable.status.in_(("scheduled", "rescheduled")),
        Payable.due_date <= ctx.today + timedelta(days=HORIZON - 1))
        .order_by(Payable.amount.desc(), Payable.due_date)).first()
    if p is None:
        return None, sup, {"error": "no_scheduled_payable", "speak": f"{sup.name} ka koi payment due nahi hai."}
    return p, sup, None


def draft_reschedule_payable(ctx: ToolContext, a: DraftRescheduleIn) -> dict:
    p, sup, err = _pick_payable(ctx, a)
    if err:
        return err
    before = ctx.radar()
    new_date = None
    if a.day_of_month:
        new_date = next_day_of_month(ctx.today, a.day_of_month)
    elif a.when:
        new_date = resolve_phrase(ctx.today, a.when)
    elif a.use_suggested_date:
        fix = next((s["fix"] for s in before["shortfalls"] if s["fix"] and s["fix"]["payable_id"] == p.id), None)
        new_date = date.fromisoformat(fix["move_to"]) if fix else None
    if new_date is None:
        return {"error": "need_date", "speak": f"{sup.name} ka payment kis tareekh ko karna hai?"}
    if new_date <= ctx.today:
        return {"error": "date_in_past", "speak": "Aage ki koi tareekh batayein."}
    after = ctx.radar({p.id: new_date})
    horizon_end = ctx.today + timedelta(days=HORIZON - 1)
    if before["flagged_days"] and not after["flagged_days"]:
        impact = "Kami door ho jayegi."
        clears = True
    elif after["flagged_days"]:
        impact = f"Phir bhi {after['shortfalls'][0]['date_text']} ko kami rahegi."
        clears = False
    else:
        impact, clears = "", False
    within = new_date <= horizon_end
    note = None if within else "Nayi tareekh 14 din ke forecast ke bahar hai."  # shown on screen, not spoken
    old = f"{p.due_date.day} {p.due_date.strftime('%b')}"
    # Kept short: the spoken read-back length drives TTS latency.
    readback = (f"{sup.name} ka {rupees(p.amount)} payment {old} se {fmt_date(new_date)} ko karna hai. "
                f"{impact} Sahi hai?").replace("  ", " ")
    action = ctx.draft("supplier", "reschedule_payable", {
        "payable_id": p.id, "supplier": sup.name, "recipient": sup.name, "amount": p.amount,
        "old_due_date": p.due_date.isoformat(), "new_due_date": new_date.isoformat(), "clears_shortfall": clears,
        "note": note}, readback)
    return {"speak": readback, "pending_action_id": action["id"], "needs_approval": True,
            "clears_shortfall": clears, "new_date": fmt_date(new_date), "within_forecast": within, "note": note}


class LogUdhaarIn(BaseModel):
    customer_name: str = Field(description="Customer as spoken, e.g. 'Sunita ji'")
    amount: int = Field(gt=0, le=200_000, description="Amount in rupees exactly as said")
    due: str = Field(description="When they will pay, as spoken: 'Friday', 'kal', '7 tareekh', or ISO date")
    phone: str | None = Field(None, description="Only if the merchant said the phone number")
    note: str = ""


def log_udhaar(ctx: ToolContext, a: LogUdhaarIn) -> dict:
    due = resolve_phrase(ctx.today, a.due)
    if due is None:
        return {"error": "need_due_date", "speak": "Kab tak denge? Din ya tareekh batayein."}
    c = find_customer(ctx.session, ctx.merchant.id, a.customer_name)
    if c is None and not a.phone:
        return {"error": "need_phone", "speak": f"{a.customer_name} naye grahak hain. Unka phone number batayein."}
    name = display_name(c.name) if c else a.customer_name.strip()
    readback = f"{rupees(a.amount)}, {name}, {due.strftime('%A')} ({due.day} {due.strftime('%b')}) tak. Sahi hai?"
    action = ctx.draft("udhaar", "log_udhaar", {
        "customer_id": c.id if c else None, "customer_name": c.name if c else a.customer_name.strip(),
        "recipient": name, "phone": a.phone, "amount": a.amount, "due_date": due.isoformat(), "note": a.note},
        readback)
    return {"speak": readback, "pending_action_id": action["id"], "needs_approval": True}


class DraftReminderIn(BaseModel):
    customer_name: str | None = Field(None, description="Customer as spoken")
    udhaar_id: int | None = None


def reminder_payload(ctx: ToolContext, u: Udhaar, c: Customer) -> dict:
    link = upi_pay_link(ctx.merchant.upi_vpa, ctx.merchant.name, u.amount, f"Udhaar {ctx.merchant.name}")
    body = reminder_text(c.language, c.name.split()[0], ctx.merchant.name, u.amount, u.due_date, link)
    return {"udhaar_id": u.id, "customer_id": c.id, "recipient": display_name(c.name), "to": c.phone,
            "amount": u.amount, "body": body, "upi_link": link}


def draft_udhaar_reminder(ctx: ToolContext, a: DraftReminderIn) -> dict:
    stmt = select(Udhaar, Customer).join(Customer).where(
        Udhaar.merchant_id == ctx.merchant.id, Udhaar.status.in_(OPEN_STATUSES))
    if a.udhaar_id:
        stmt = stmt.where(Udhaar.id == a.udhaar_id)
    elif a.customer_name:
        c = find_customer(ctx.session, ctx.merchant.id, a.customer_name)
        if c is None:
            return {"error": "customer_not_found", "speak": f"{a.customer_name} ka udhaar nahi mila."}
        stmt = stmt.where(Udhaar.customer_id == c.id)
    else:
        return {"error": "need_customer", "speak": "Kise reminder bhejna hai?"}
    row = ctx.session.exec(stmt.order_by(Udhaar.due_date)).first()
    if row is None:
        return {"error": "no_open_udhaar", "speak": "Is grahak ka koi khula udhaar nahi hai."}
    u, c = row
    payload = reminder_payload(ctx, u, c)
    readback = f"{payload['recipient']} ko {rupees(u.amount)} ka reminder UPI link ke saath bhejna hai. Sahi hai?"
    action = ctx.draft("udhaar", "send_reminder", payload, readback)
    auto = ctx.auto_execute_last()
    if auto:
        return {"speak": auto["confirmation_text"] + " (Auto mode)", "pending_action_id": action["id"],
                "needs_approval": False, "auto_executed": True, "message_preview": payload["body"]}
    return {"speak": readback, "pending_action_id": action["id"], "needs_approval": True,
            "message_preview": payload["body"]}


class DraftWinbackIn(BaseModel):
    discount_pct: int = Field(10, ge=1, le=50, description="Offer discount percent")
    customer_ids: list[int] | None = Field(None, description="Optional subset of lapsed customer ids")


def draft_winback(ctx: ToolContext, a: DraftWinbackIn) -> dict:
    lapsed = lapsed_regulars(ctx.session, ctx.merchant.id, ctx.today)
    if a.customer_ids:
        lapsed = [r for r in lapsed if r["customer_id"] in set(a.customer_ids)]
    consented = [r for r in lapsed if r["opted_in"]]  # consent: opted-in customers only
    if not consented:
        return {"error": "no_opted_in", "speak": "Koi opted-in purana grahak nahi mila."}
    messages = []
    for r in consented:
        c = ctx.session.get(Customer, r["customer_id"])
        messages.append({"customer_id": c.id, "name": display_name(c.name), "to": c.phone,
                         "body": winback_text(c.language, c.name.split()[0], ctx.merchant.name, a.discount_pct)})
    n, skipped = len(messages), len(lapsed) - len(consented)
    readback = f"{n} purane regular grahakon ko {a.discount_pct}% chhoot ka offer message bhejna hai. Sahi hai?"
    action = ctx.draft("growth", "send_winback", {
        "customer_ids": [m["customer_id"] for m in messages], "messages": messages, "count": n,
        "recipient": f"{n} grahak", "discount_pct": a.discount_pct, "skipped_not_opted_in": skipped}, readback)
    auto = ctx.auto_execute_last()
    if auto:
        return {"speak": auto["confirmation_text"] + " (Auto mode)", "pending_action_id": action["id"],
                "needs_approval": False, "auto_executed": True, "recipients": n,
                "skipped_not_opted_in": skipped, "message_preview": messages[0]["body"]}
    return {"speak": readback, "pending_action_id": action["id"], "needs_approval": True, "recipients": n,
            "skipped_not_opted_in": skipped, "message_preview": messages[0]["body"]}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_sales_summary", "Yesterday's and today's sales vs a usual day.", NoArgs, get_sales_summary),
    Tool("get_cash_radar", "14-day cash forecast: balance, shortfall days, the payable causing it, suggested fix.",
         NoArgs, get_cash_radar),
    Tool("list_payables", "Upcoming supplier payments.", ListPayablesIn, list_payables),
    Tool("draft_supplier_payment", "Draft (not send) a payment to a supplier. Returns a read-back for approval.",
         DraftPaymentIn, draft_supplier_payment),
    Tool("draft_reschedule_payable", "Draft (not apply) moving a supplier payment to another date. "
         "Pass the date as spoken (day_of_month or when); never compute dates yourself.",
         DraftRescheduleIn, draft_reschedule_payable),
    Tool("log_udhaar", "Draft an udhaar (customer credit) entry with read-back. Pass the due date as spoken.",
         LogUdhaarIn, log_udhaar),
    Tool("list_udhaar", "Open udhaar entries and totals.", ListUdhaarIn, list_udhaar_tool),
    Tool("draft_udhaar_reminder", "Draft a reminder message with a UPI pay link for an open udhaar.",
         DraftReminderIn, draft_udhaar_reminder),
    Tool("get_growth_insights", "Peak hours, slow days, festival vs last year, lapsed regular customers.",
         NoArgs, get_growth_insights),
    Tool("draft_winback", "Draft a win-back offer message to lapsed regulars who opted in.",
         DraftWinbackIn, draft_winback),
    Tool("get_morning_briefing", "Subah ki Report: yesterday's sales, payments due, udhaar to collect, one tip.",
         NoArgs, get_morning_briefing),
]}


def tool_schemas() -> list[dict]:
    return [t.schema() for t in TOOLS.values()]
