"""Cash Radar: daily inflow forecast (LightGBM quantiles), baseline, backtest, shortfall detection.

Every number the radar returns is computed here; the agent only reads it out.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Merchant, Payable, Supplier, Transaction
from app.services.fmt import fmt_date, rupees as _fmt_rupees
from app.services.festivals import days_to_next_festival, festival_on, load_festivals
from app.services.sales import daily_inflows

QUANTILES = {"p10": 0.10, "p50": 0.50, "p90": 0.90}
HORIZON = 14
MIN_HISTORY = 28
FEATURES = ["dow", "dom", "month_start", "month_end", "festival", "days_to_festival", "post_festival",
            "lag7", "lag14", "lag28", "same_wd_mean", "roll7", "roll28"]
NUM_ROUNDS = 300
LGB_PARAMS = dict(learning_rate=0.04, num_leaves=7, min_data_in_leaf=8, bagging_fraction=0.85,
                  bagging_freq=1, feature_fraction=0.9, lambda_l2=1.0, seed=7, num_threads=1,
                  deterministic=True, force_row_wise=True, verbosity=-1)


# ---------------------------------------------------------------- features


def _is_month_end(d: date) -> bool:
    return (d + timedelta(days=2)).month != d.month


def _post_festival(d: date) -> bool:
    return any(f.end < d <= f.end + timedelta(days=2) for f in load_festivals())


def calendar_features(d: date) -> dict:
    return {"dow": d.weekday(), "dom": d.day, "month_start": int(d.day <= 5), "month_end": int(_is_month_end(d)),
            "festival": int(festival_on(d) is not None), "days_to_festival": days_to_next_festival(d),
            "post_festival": int(_post_festival(d))}


def feature_row(d: date, series: dict[date, float]) -> dict:
    def s(k: int) -> float:
        return series[d - timedelta(days=k)]

    row = calendar_features(d)
    row.update(lag7=s(7), lag14=s(14), lag28=s(28), same_wd_mean=(s(7) + s(14) + s(21) + s(28)) / 4,
               roll7=sum(s(k) for k in range(1, 8)) / 7, roll28=sum(s(k) for k in range(1, 29)) / 28)
    return row


def training_frame(series: dict[date, float], until: date) -> pd.DataFrame:
    days = sorted(d for d in series if d < until)
    rows = []
    for d in days[MIN_HISTORY:]:
        r = feature_row(d, series)
        r["y"] = series[d]
        r["date"] = d
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- model


@dataclass
class QuantileModel:
    models: dict[str, lgb.Booster]

    @classmethod
    def fit(cls, frame: pd.DataFrame) -> "QuantileModel":
        X, y = frame[FEATURES].astype(float), frame["y"].astype(float)
        models = {}
        for name, alpha in QUANTILES.items():
            params = dict(LGB_PARAMS, objective="quantile", alpha=alpha)
            models[name] = lgb.train(params, lgb.Dataset(X, y, free_raw_data=False), num_boost_round=NUM_ROUNDS)
        return cls(models)

    def predict_row(self, row: dict) -> dict[str, float]:
        X = pd.DataFrame([row])[FEATURES].astype(float)
        preds = sorted(max(0.0, float(m.predict(X)[0])) for m in self.models.values())
        return dict(zip(QUANTILES, preds))  # sorted => p10 <= p50 <= p90


def forecast_days(model: QuantileModel, series: dict[date, float], start: date, horizon: int) -> list[dict]:
    """Recursive multi-step forecast: lags beyond known history are filled with p50."""
    filled = dict(series)
    out = []
    for k in range(horizon):
        d = start + timedelta(days=k)
        q = model.predict_row(feature_row(d, filled))
        filled[d] = q["p50"]
        out.append({"date": d, **q})
    return out


def baseline_days(series: dict[date, float], start: date, horizon: int) -> list[float]:
    """Same day last week (repeated weekly when last week is also in the future)."""
    out = []
    for k in range(horizon):
        d = start + timedelta(days=k)
        ref = d - timedelta(days=7)
        while ref >= start:
            ref -= timedelta(days=7)
        out.append(series[ref])
    return out


# ---------------------------------------------------------------- data access + cache

_model_cache: dict[tuple, QuantileModel] = {}
_backtest_cache: dict[tuple, dict] = {}


def history_series(session: Session, merchant_id: int, until: date) -> dict[date, float]:
    first = session.exec(select(func.min(Transaction.ts)).where(Transaction.merchant_id == merchant_id)).one()
    if first is None:
        return {}
    first_d = first.date() if isinstance(first, datetime) else datetime.fromisoformat(str(first)).date()
    return {d: float(v) for d, v in daily_inflows(session, merchant_id, first_d, until).items()}


def get_model(session: Session, merchant_id: int, today: date) -> tuple[QuantileModel, dict[date, float]]:
    series = history_series(session, merchant_id, today)
    key = (merchant_id, today, len(series), round(sum(series.values())))
    if key not in _model_cache:
        _model_cache.clear() if len(_model_cache) > 8 else None
        _model_cache[key] = QuantileModel.fit(training_frame(series, today))
    return _model_cache[key], series


# ---------------------------------------------------------------- backtest


def mae_mape(actual: list[float], pred: list[float]) -> dict:
    a, p = np.array(actual, dtype=float), np.array(pred, dtype=float)
    mask = a > 0
    return {"mae": int(round(float(np.mean(np.abs(a - p))))),
            "mape": round(float(np.mean(np.abs(a[mask] - p[mask]) / a[mask])) * 100, 1)}


def backtest(session: Session, merchant_id: int, today: date, window: int = 60, step: int = 7,
             horizon: int = 7) -> dict:
    """Rolling origin over the last `window` days: refit at each origin, forecast `horizon` days."""
    series = history_series(session, merchant_id, today)
    key = (merchant_id, today, len(series), window, step, horizon)
    if key in _backtest_cache:
        return _backtest_cache[key]
    start = today - timedelta(days=window)
    actual, model_pred, base_pred, origins, inside = [], [], [], [], 0
    origin = start
    while origin < today:
        h = min(horizon, (today - origin).days)
        model = QuantileModel.fit(training_frame(series, origin))
        fc = forecast_days(model, series, origin, h)
        base = baseline_days(series, origin, h)
        for k in range(h):
            d = origin + timedelta(days=k)
            actual.append(series[d])
            model_pred.append(fc[k]["p50"])
            base_pred.append(base[k])
            inside += int(fc[k]["p10"] <= series[d] <= fc[k]["p90"])
        origins.append(origin.isoformat())
        origin += timedelta(days=step)
    m, b = mae_mape(actual, model_pred), mae_mape(actual, base_pred)
    coverage = round(inside * 100 / len(actual), 1) if actual else None
    result = {"merchant_id": merchant_id, "window_days": window, "origins": origins, "step_days": step,
              "horizon_days": horizon, "n_points": len(actual), "model": m, "baseline": b,
              "baseline_name": "same day last week", "beats_baseline": m["mae"] < b["mae"] and m["mape"] < b["mape"],
              "mae_improvement_pct": int(round((b["mae"] - m["mae"]) * 100 / b["mae"])) if b["mae"] else None,
              "p10_p90_coverage": coverage}
    _backtest_cache[key] = result
    return result


# ---------------------------------------------------------------- radar


def current_balance(session: Session, merchant: Merchant, demo_start: date, now: datetime) -> int:
    start = datetime.combine(demo_start, time.min)
    rows = session.exec(select(Transaction.direction, func.coalesce(func.sum(Transaction.amount), 0))
                        .where(Transaction.merchant_id == merchant.id, Transaction.ts >= start,
                               Transaction.ts <= now).group_by(Transaction.direction)).all()
    net = {d: int(v) for d, v in rows}
    return merchant.opening_balance + net.get("in", 0) - net.get("out", 0)


def scheduled_payables(session: Session, merchant_id: int, until: date) -> list[dict]:
    rows = session.exec(select(Payable, Supplier).join(Supplier).where(
        Payable.merchant_id == merchant_id, Payable.status.in_(("scheduled", "rescheduled")),
        Payable.due_date <= until).order_by(Payable.due_date, Payable.id)).all()
    return [{"id": p.id, "supplier": s.name, "supplier_id": s.id, "amount": p.amount, "due_date": p.due_date}
            for p, s in rows]


def project(balance_now: int, buffer: int, fc: list[dict], payables: list[dict], today: date,
            moves: dict[int, date] | None = None) -> list[dict]:
    """Projected end-of-day balances. `moves` maps payable id -> new due date (what-if)."""
    moves = moves or {}
    by_day: dict[date, list[dict]] = {}
    for p in payables:
        due = moves.get(p["id"], p["due_date"])
        by_day.setdefault(max(due, today), []).append(p)
    b = {"p10": balance_now, "p50": balance_now, "p90": balance_now}
    days = []
    for f in fc:
        d = f["date"]
        dues = by_day.get(d, [])
        out_total = sum(p["amount"] for p in dues)
        for q in b:
            b[q] = b[q] + int(round(f[q])) - out_total
        days.append({"date": d.isoformat(), "weekday": d.strftime("%a"),
                     "inflow_p10": int(round(f["p10"])), "inflow_p50": int(round(f["p50"])),
                     "inflow_p90": int(round(f["p90"])), "payables_total": out_total,
                     "payables": [{"id": p["id"], "supplier": p["supplier"], "amount": p["amount"]} for p in dues],
                     "balance_p10": b["p10"], "balance_p50": b["p50"], "balance_p90": b["p90"],
                     "below_buffer": b["p10"] < buffer})
    return days


def find_safe_date(balance_now: int, buffer: int, fc: list[dict], payables: list[dict], today: date,
                   payable: dict, horizon_end: date) -> tuple[date, bool]:
    """First date after the payable's due date where moving it leaves no day below buffer."""
    d = payable["due_date"] + timedelta(days=1)
    while d <= horizon_end:
        days = project(balance_now, buffer, fc, payables, today, {payable["id"]: d})
        if not any(x["below_buffer"] for x in days):
            return d, True
        d += timedelta(days=1)
    return horizon_end + timedelta(days=1), False


def cash_radar(session: Session, merchant: Merchant, today: date, now: datetime, demo_start: date,
               moves: dict[int, date] | None = None) -> dict:
    model, series = get_model(session, merchant.id, today)
    fc = forecast_days(model, series, today, HORIZON)
    today_in = daily_inflows(session, merchant.id, today, today + timedelta(days=1))[today]
    for q in QUANTILES:  # day 0: only what's still expected today
        fc[0][q] = max(fc[0][q] - today_in, 0.0)
    horizon_end = today + timedelta(days=HORIZON - 1)
    balance = current_balance(session, merchant, demo_start, now)
    payables = scheduled_payables(session, merchant.id, horizon_end)
    days = project(balance, merchant.cash_buffer, fc, payables, today, moves)

    shortfalls, i = [], 0
    while i < len(days):
        if not days[i]["below_buffer"]:
            i += 1
            continue
        j = i
        while j + 1 < len(days) and days[j + 1]["below_buffer"]:
            j += 1
        first = days[i]
        d0 = date.fromisoformat(first["date"])
        candidates = [p for p in payables if max((moves or {}).get(p["id"], p["due_date"]), today) <= d0]
        same_day = [p for p in candidates if max((moves or {}).get(p["id"], p["due_date"]), today) == d0]
        cause = max(same_day or candidates, key=lambda p: p["amount"], default=None)
        low = min(days[i:j + 1], key=lambda x: x["balance_p10"])
        sf = {"date": first["date"], "date_text": fmt_date(d0), "days_ahead": (d0 - today).days,
              "last_day": days[j]["date"], "n_days": j - i + 1, "lowest_balance_p10": low["balance_p10"],
              "gap": merchant.cash_buffer - low["balance_p10"], "cause": None, "fix": None}
        if cause:
            sf["cause"] = {"payable_id": cause["id"], "supplier": cause["supplier"], "amount": cause["amount"],
                           "due_date": cause["due_date"].isoformat()}
            eff = dict(cause, due_date=max((moves or {}).get(cause["id"], cause["due_date"]), today))
            safe, within = find_safe_date(balance, merchant.cash_buffer, fc, payables, today, eff, horizon_end)
            sf["fix"] = {"payable_id": cause["id"], "move_to": safe.isoformat(), "move_to_text": fmt_date(safe),
                         "days_later": (safe - eff["due_date"]).days, "within_forecast": within,
                         "text": f"{cause['supplier']} ka {_fmt_rupees(cause['amount'])} payment "
                                 f"{fmt_date(safe)} ko karein to balance buffer se upar rahega."}
        shortfalls.append(sf)
        i = j + 1

    if shortfalls:
        s = shortfalls[0]
        summary = (f"{s['date_text']} ko balance {_fmt_rupees(s['lowest_balance_p10'])} tak gir sakta hai, "
                   f"buffer {_fmt_rupees(merchant.cash_buffer)} se {_fmt_rupees(s['gap'])} kam.")
        if s["fix"]:
            summary += " " + s["fix"]["text"]
    else:
        lowest = min(days, key=lambda x: x["balance_p10"])
        summary = (f"Agle {HORIZON} din balance buffer {_fmt_rupees(merchant.cash_buffer)} se upar rahega. "
                   f"Sabse kam {_fmt_rupees(lowest['balance_p10'])}, {fmt_date(date.fromisoformat(lowest['date']))} ko.")
    return {"merchant_id": merchant.id, "as_of": now.isoformat(), "balance_now": balance,
            "balance_now_text": _fmt_rupees(balance), "buffer": merchant.cash_buffer, "horizon_days": HORIZON,
            "days": days, "flagged_days": [d["date"] for d in days if d["below_buffer"]],
            "shortfalls": shortfalls, "summary_text": summary,
            "method": "LightGBM quantile forecast (p10/p50/p90); pessimistic line uses p10 inflows."}

