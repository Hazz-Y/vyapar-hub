"""Deterministic synthetic data for the demo.

ALL DATA PRODUCED HERE IS SYNTHETIC. Names, phone numbers, VPAs, amounts and patterns
are invented for the demo and are not real research or real merchant data.

History covers HISTORY_DAYS days ending the day before the demo date (the demo starts at
shop opening, so "today" has no payments yet). 400 days rather than 365 so that the
year-over-year festival comparison has last year's festival in range.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import numpy as np
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from app import models
from app.services.festivals import festival_on, load_festivals

SEED = 20240601
HISTORY_DAYS = 400
PAYER_SALT = "vyapar-demo-salt"
DEMO_START_TIME = time(8, 30)
HORIZON_DAYS = 14

# The planted shortfall (main demo merchant).
PLANTED_SUPPLIER = "Agarwal Traders"
PLANTED_AMOUNT = 22_000
PLANTED_DAY = 5
N_LAPSED = 14


def hash_payer(vpa: str) -> str:
    """Payer IDs are stored only as salted hashes, never as raw VPAs."""
    return hashlib.sha256(f"{PAYER_SALT}:{vpa.lower()}".encode()).hexdigest()[:20]


# ---------------------------------------------------------------- profiles


@dataclass
class SupplierSpec:
    name: str
    contact: str
    category: str
    cadence: str  # daily | every2 | weekly:<0-6> | every14 | every20
    share: float  # fraction of period inflow paid to this supplier
    gst_rate: int
    gstin: str | None
    aliases: list[str]
    hard_alias: str | None = None  # needs the LLM fallback to match


@dataclass
class Profile:
    key: str
    name: str
    owner: str
    shop_type: str
    city: str
    language: str
    vpa: str
    buffer: int
    opening_balance: int
    opening_time: str
    hours: dict[int, float]
    dow: tuple[float, ...]  # Mon..Sun
    fest_boost: dict[str, float]
    walkin_per_day: float
    walkin_ticket: float
    regular_ticket: float
    occasional_ticket: float
    regular_p: tuple[float, float]
    ticket_sigma: float
    round_to: int
    trend_per_year: float
    first_names: list[str]
    surnames: list[str]
    customer_language: str
    suppliers: list[SupplierSpec] = field(default_factory=list)


HINDI_FIRST = [
    "Amit", "Anita", "Arjun", "Asha", "Deepak", "Geeta", "Kamla", "Kavita", "Manoj", "Meena",
    "Mohan", "Neha", "Pankaj", "Pooja", "Priya", "Rajesh", "Rakesh", "Rekha", "Rohit", "Sanjay",
    "Santosh", "Savita", "Seema", "Shyam", "Suresh", "Usha", "Vijay", "Vikas", "Anil", "Babita",
    "Dinesh", "Gopal", "Hari", "Jyoti", "Kiran", "Lalit", "Mukesh", "Nisha", "Om", "Pushpa",
    "Radha", "Ravi", "Sarita", "Shalini", "Sushil", "Uma", "Vandana", "Yogesh", "Alok", "Kusum",
]
HINDI_SURNAME = [
    "Verma", "Mishra", "Pandey", "Yadav", "Shukla", "Tripathi", "Srivastava", "Dubey",
    "Saxena", "Chauhan", "Kushwaha", "Rajput", "Awasthi", "Dixit", "Bajpai", "Kanaujia",
]
TAMIL_FIRST = [
    "Arun", "Bala", "Deepa", "Divya", "Ganesh", "Gowri", "Hari", "Indira", "Janaki", "Karthik",
    "Kavitha", "Lakshman", "Mani", "Meenakshi", "Murali", "Nandhini", "Padma", "Prakash", "Priya",
    "Raja", "Ramya", "Saravanan", "Selvi", "Senthil", "Shanthi", "Siva", "Suresh", "Tamil",
    "Uma", "Vasanth", "Vijay", "Yamuna", "Anand", "Bharathi", "Chitra", "Dinesh", "Geetha",
    "Kumar", "Lalitha", "Mohan", "Nirmala", "Pandian", "Revathi", "Sathya", "Thenmozhi",
    "Valli", "Velu", "Kannan", "Malar", "Ravi",
]
TAMIL_SURNAME = [
    "Iyer", "Pillai", "Raman", "Subramanian", "Krishnan", "Natarajan", "Sundaram", "Murugan",
    "Rajan", "Venkatesan", "Shankar", "Ganesan", "Arumugam", "Balan", "Chandran", "Durai",
]

RAMESH = Profile(
    key="ramesh",
    name="Ramesh Kirana Store",
    owner="Ramesh Tiwari",
    shop_type="kirana",
    city="Kanpur",
    language="hi",
    vpa="rameshkirana@paytm",
    buffer=5_000,
    opening_balance=16_000,
    opening_time="08:00",
    hours={7: .6, 8: 1.2, 9: 1.4, 10: 1.0, 11: .7, 12: .6, 13: .5, 14: .4, 15: .5, 16: .7,
           17: 1.0, 18: 1.4, 19: 1.6, 20: 1.3, 21: .7},
    dow=(0.95, 0.82, 0.95, 0.97, 1.0, 1.1, 1.2),
    fest_boost={"Diwali": 1.9, "Holi": 1.5, "Eid al-Fitr": 1.3, "Navratri": 1.25,
                "Raksha Bandhan": 1.35, "Pongal": 1.05},
    walkin_per_day=45, walkin_ticket=110, regular_ticket=165, occasional_ticket=200,
    regular_p=(0.3, 0.6), ticket_sigma=0.5, round_to=1, trend_per_year=0.08,
    first_names=[n for n in HINDI_FIRST if n != "Sunita"], surnames=HINDI_SURNAME,
    customer_language="hi",
    suppliers=[
        SupplierSpec("Agarwal Traders", "Mahesh Agarwal", "wholesale grocery", "every14", 0.10, 5,
                     "09AAKFA1234Q1Z5", ["Agarwal Traders", "AGARWAL TRADERS KANPUR",
                                         "agarwaltraders@okhdfcbank", "Agarwal Trdrs"], "M/S A.T. KNP"),
        SupplierSpec("Sharma Milk Dairy", "Vinod Sharma", "dairy", "daily", 0.15, 0,
                     None, ["Sharma Milk Dairy", "SHARMA DAIRY", "sharmadairy@ybl",
                            "Sharma Milk Dairy Kanpur"], "S.D. MILK"),
        SupplierSpec("Verma Agencies", "Rajiv Verma", "FMCG distributor", "weekly:3", 0.15, 18,
                     "09ABCPV5678K1Z2", ["Verma Agencies", "VERMA AGENCIES HUL DIST",
                                         "vermaagencies@okaxis", "Verma Agncy"], "VA KNP DIST"),
        SupplierSpec("Gupta Oil Mills", "Sunil Gupta", "edible oil", "weekly:0", 0.10, 5,
                     "09AAGFG4321M1Z9", ["Gupta Oil Mills", "GUPTA OIL MILL", "guptaoil@paytm",
                                         "Gupta Oil Mills Pvt"], None),
        SupplierSpec("Yadav Atta Chakki", "Ramu Yadav", "flour", "weekly:5", 0.10, 5, None,
                     ["Yadav Atta Chakki", "YADAV ATTA", "yadavatta@ybl", "Yadav Aata Chakki"], None),
        SupplierSpec("Modern Bakery", "Imran Khan", "bakery", "every2", 0.05, 5, None,
                     ["Modern Bakery", "MODERN BAKERY KNP", "modernbakery@okicici", "Modern Bakers"], None),
        SupplierSpec("Singh Beverages", "Harpreet Singh", "cold drinks", "weekly:2", 0.08, 28,
                     "09BBSPS9876L1Z1", ["Singh Beverages", "SINGH BEVERAGES", "singhbev@okhdfcbank",
                                         "Singh Bevrages"], None),
        SupplierSpec("Jain Namkeen", "Prakash Jain", "snacks", "weekly:1", 0.07, 12, None,
                     ["Jain Namkeen", "JAIN NAMKEEN BHANDAR", "jainnamkeen@paytm", "Jain Namkin"], None),
    ],
)

LAKSHMI = Profile(
    key="lakshmi",
    name="Lakshmi Tea Stall",
    owner="Lakshmi Narayanan",
    shop_type="tea stall",
    city="Chennai",
    language="ta",
    vpa="lakshmitea@paytm",
    buffer=2_000,
    opening_balance=9_000,
    opening_time="06:00",
    hours={6: .9, 7: 1.6, 8: 1.8, 9: 1.3, 10: .8, 11: .7, 12: .6, 13: .6, 14: .5, 15: .8,
           16: 1.4, 17: 1.6, 18: 1.2, 19: .8, 20: .5, 21: .3},
    dow=(1.05, 1.05, 1.05, 1.05, 1.05, 0.92, 0.75),
    fest_boost={"Pongal": 1.6, "Diwali": 1.3, "Navratri": 1.12, "Holi": 1.02,
                "Eid al-Fitr": 1.08, "Raksha Bandhan": 1.02},
    walkin_per_day=110, walkin_ticket=22, regular_ticket=28, occasional_ticket=35,
    regular_p=(0.45, 0.8), ticket_sigma=0.35, round_to=5, trend_per_year=0.05,
    first_names=TAMIL_FIRST, surnames=TAMIL_SURNAME, customer_language="ta",
    suppliers=[
        SupplierSpec("Aavin Milk Agency", "Selvam", "dairy", "daily", 0.25, 0, None,
                     ["Aavin Milk Agency", "AAVIN MILK", "aavinagency@ybl", "Aavin Milk Agncy"], None),
        SupplierSpec("Chennai Tea Traders", "Rafiq", "tea powder", "weekly:0", 0.12, 5,
                     "33AACCC1111T1Z3", ["Chennai Tea Traders", "CHENNAI TEA TRADERS",
                                         "chennaitea@okaxis", "Chennai Tea Trdrs"], None),
        SupplierSpec("Sakthi Sugar Depot", "Muthu", "sugar", "weekly:3", 0.06, 5, None,
                     ["Sakthi Sugar Depot", "SAKTHI SUGAR", "sakthisugar@paytm", "Sakthi Sugars"], None),
        SupplierSpec("Murugan Snacks", "Murugan", "snacks", "every2", 0.10, 12, None,
                     ["Murugan Snacks", "MURUGAN SNACKS", "murugansnacks@ybl", "Murugan Snaks"], None),
        SupplierSpec("Indane Gas Agency", "Office", "LPG", "every20", 0.06, 18, "33AAACI2222G1Z8",
                     ["Indane Gas Agency", "INDANE GAS", "indanegas@okicici", "Indane Gas Agncy"], None),
        SupplierSpec("Sri Balaji Cups", "Balaji", "paper cups", "weekly:5", 0.03, 18, None,
                     ["Sri Balaji Cups", "SRI BALAJI CUPS", "balajicups@paytm", "Balaji Cups"], None),
        SupplierSpec("Annapoorna Bakery", "Ravi", "bakery", "every2", 0.06, 5, None,
                     ["Annapoorna Bakery", "ANNAPOORNA BAKERY", "annapoorna@ybl", "Annapurna Bakery"], None),
        SupplierSpec("Kumar Provisions", "Kumar", "groceries", "weekly:2", 0.05, 5, None,
                     ["Kumar Provisions", "KUMAR PROVISIONS", "kumarprov@okhdfcbank", "Kumar Provision"], None),
    ],
)

PROFILES = [RAMESH, LAKSHMI]

# Udhaar book for the main merchant: (first name, amount, due offset days, created offset days)
RAMESH_UDHAAR = [
    ("Anita", 1200, 0, -6), ("Manoj", 340, 0, -3), ("Kamla", 850, 2, -5), ("Deepak", 2400, 4, -12),
    ("Geeta", 180, 6, -2), ("Rakesh", 560, 8, -4), ("Savita", 1500, 10, -9), ("Pankaj", 275, 12, -1),
    ("Usha", 920, 15, -7),
]
SUNITA = ("Sunita", "Sunita Verma", 650)

# Ramesh's end-of-day pessimistic balance targets for horizon days 0..4; day 5 lands below buffer.
RAMESH_PRE_TARGETS = [15_800, 14_600, 16_000, 14_900, 15_400]
RAMESH_BREACH_BELOW_BUFFER = 14_000
RAMESH_RECOVERY_PER_DAY = 8_000
PESSIMISTIC_FACTOR = 0.8


# ---------------------------------------------------------------- demand model


def next_friday(d: date) -> date:
    ahead = (4 - d.weekday()) % 7
    return d + timedelta(days=ahead or 7)


def month_factor(d: date) -> float:
    days_in_month = ((d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
    if d.day <= 5:
        return 1.15  # salary credited at month end, spent in the first days
    if d.day >= days_in_month - 1:
        return 1.08
    if 20 <= d.day <= 27:
        return 0.95
    return 1.0


def festival_factor(p: Profile, d: date) -> float:
    f = festival_on(d)
    if f is not None:
        boost = p.fest_boost.get(f.name, 1.0)
        if d < f.day:
            return 1 + (boost - 1) * (1 - (f.day - d).days / (f.lead_days + 1))
        return boost
    for f in load_festivals():
        if f.end + timedelta(days=1) == d:
            return 0.85  # post-festival lull
    return 1.0


def slow_week_factor(d: date, demo: date) -> float:
    for offset in (103, 190, 265):
        start = demo - timedelta(days=offset)
        if start <= d < start + timedelta(days=7):
            return 0.7
    return 1.0


def day_multiplier(p: Profile, d: date, demo: date) -> float:
    trend = 1 - p.trend_per_year * (demo - d).days / 365
    return p.dow[d.weekday()] * month_factor(d) * festival_factor(p, d) * slow_week_factor(d, demo) * trend


# ---------------------------------------------------------------- generator


class Builder:
    def __init__(self, demo: date):
        self.demo = demo
        self.rows: dict[str, list[dict]] = {t: [] for t in (
            "merchant", "transaction", "supplier", "payable", "customer", "udhaar", "settings")}
        self.txn_id = 0
        self.payable_id = 0
        self.supplier_id = 0
        self.customer_id = 0
        self.udhaar_id = 0

    # --- helpers
    def _amount(self, rng: np.random.Generator, mean: float, sigma: float, round_to: int) -> int:
        v = mean * math.exp(rng.normal(-sigma * sigma / 2, sigma))
        v = max(10, v)
        return int(round(v / round_to) * round_to) if round_to > 1 else int(round(v))

    def _ts(self, rng: np.random.Generator, p: Profile, d: date) -> datetime:
        hours = list(p.hours)
        w = np.array([p.hours[h] for h in hours])
        h = int(rng.choice(hours, p=w / w.sum()))
        return datetime.combine(d, time(h, int(rng.integers(0, 60)), int(rng.integers(0, 60))))

    def _add_txn(self, mid: int, ts: datetime, amount: int, direction: str, source: str,
                 payer_hash: str | None = None, counterparty: str | None = None, note: str | None = None) -> int:
        self.txn_id += 1
        self.rows["transaction"].append(dict(
            id=self.txn_id, merchant_id=mid, ts=ts, amount=amount, direction=direction,
            payer_hash=payer_hash, counterparty=counterparty, note=note, source=source))
        return self.txn_id

    # --- merchant
    def build_merchant(self, mid: int, p: Profile) -> None:
        rng = np.random.default_rng(SEED + mid)
        self.rows["merchant"].append(dict(
            id=mid, name=p.name, owner_name=p.owner, shop_type=p.shop_type, city=p.city,
            language=p.language, upi_vpa=p.vpa, cash_buffer=p.buffer,
            opening_balance=p.opening_balance, opening_time=p.opening_time))
        self.rows["settings"].append(dict(
            merchant_id=mid, autonomy_udhaar="auto" if p is RAMESH else "suggest", autonomy_growth="suggest",
            autonomy_supplier="suggest", autonomy_cash="suggest", language=p.language))

        days = [self.demo - timedelta(days=HISTORY_DAYS - i) for i in range(HISTORY_DAYS)]
        mult = np.array([day_multiplier(p, d, self.demo) for d in days])
        customers = self._build_customers(mid, p, rng)
        daily_in = self._build_inflows(mid, p, rng, days, mult, customers)
        self._build_suppliers(mid, p, rng, days, daily_in, mult)
        if p is RAMESH:
            self._build_udhaar(mid, customers)

    def _build_customers(self, mid: int, p: Profile, rng: np.random.Generator) -> list[dict]:
        combos = [(f, s) for f in p.first_names for s in p.surnames]
        order = rng.permutation(len(combos))
        names = [f"{combos[i][0]} {combos[i][1]}" for i in order[:400]]
        if p is RAMESH:
            names[0] = SUNITA[1]  # a regular, so her payments carry a known payer hash
        n_reg = 120
        customers = []
        for i, name in enumerate(names):
            self.customer_id += 1
            vpa = f"{name.lower().replace(' ', '.')}{int(rng.integers(10, 99))}@upi"
            phone = "+91" + str(int(rng.integers(7_000_000_000, 9_999_999_999)))
            c = dict(id=self.customer_id, merchant_id=mid, name=name, phone=phone,
                     payer_hash=hash_payer(vpa), opted_in=bool(rng.random() < 0.6),
                     language=p.customer_language)
            if p is RAMESH and i == 0:
                c["opted_in"] = True
            customers.append(c)
            c_meta = dict(c, regular=i < n_reg)
            customers[-1] = c_meta
        self.rows["customer"].extend({k: v for k, v in c.items() if k != "regular"} for c in customers)
        return customers

    def _build_inflows(self, mid: int, p: Profile, rng: np.random.Generator, days: list[date],
                       mult: np.ndarray, customers: list[dict]) -> np.ndarray:
        n_days = len(days)
        regulars = [c for c in customers if c["regular"]]
        occasional = [c for c in customers if not c["regular"]]
        n_reg = len(regulars)

        # Regular visits: daily Bernoulli with a personal propensity.
        p_i = rng.uniform(*p.regular_p, size=n_reg)
        prob = np.clip(p_i[:, None] * np.sqrt(mult)[None, :], 0, 0.95)
        visits = rng.random((n_reg, n_days)) < prob

        lapsed_idx: list[int] = []
        if p is RAMESH:
            # 14 regulars stop coming 3-5 weeks before the demo date (index 0 is Sunita: skip).
            udhaar_names = {u[0] for u in RAMESH_UDHAAR}
            pool = [i for i in range(1, n_reg) if regulars[i]["name"].split()[0] not in udhaar_names]
            lapsed_idx = sorted(rng.choice(pool, size=N_LAPSED, replace=False).tolist())
            for i in lapsed_idx:
                last = n_days - int(rng.integers(22, 36))
                visits[i, last + 1:] = False
                visits[i, last] = True
        for i in range(n_reg):
            if i not in lapsed_idx and not visits[i, -10:].any():
                visits[i, n_days - 1 - int(rng.integers(0, 10))] = True

        daily_in = np.zeros(n_days)
        noise = np.exp(rng.normal(0, 0.07, size=n_days))
        for di, d in enumerate(days):
            ticket_scale = math.sqrt(mult[di]) * noise[di]
            for i in np.flatnonzero(visits[:, di]):
                amt = self._amount(rng, p.regular_ticket * ticket_scale, p.ticket_sigma, p.round_to)
                self._add_txn(mid, self._ts(rng, p, d), amt, "in", "qr", regulars[i]["payer_hash"])
                daily_in[di] += amt
            n_walk = rng.poisson(p.walkin_per_day * mult[di] * noise[di])
            for k in range(n_walk):
                amt = self._amount(rng, p.walkin_ticket * ticket_scale, p.ticket_sigma, p.round_to)
                h = hash_payer(f"walkin-{mid}-{di}-{k}@upi")
                self._add_txn(mid, self._ts(rng, p, d), amt, "in", "qr", h)
                daily_in[di] += amt

        # Occasional customers: one visit every 35-75 days, so never >=4 visits in 90 days.
        for c in occasional:
            di = int(rng.integers(0, 60))
            while di < n_days:
                amt = self._amount(rng, p.occasional_ticket * math.sqrt(mult[di]), p.ticket_sigma, p.round_to)
                self._add_txn(mid, self._ts(rng, p, days[di]), amt, "in", "qr", c["payer_hash"])
                daily_in[di] += amt
                di += int(rng.integers(35, 76))
        return daily_in

    def _build_suppliers(self, mid: int, p: Profile, rng: np.random.Generator, days: list[date],
                         daily_in: np.ndarray, mult: np.ndarray) -> None:
        demo = self.demo
        horizon = [demo + timedelta(days=k) for k in range(HORIZON_DAYS)]
        # Expected inflow per horizon day: recent level (de-seasonalised) x day multiplier.
        level = float(np.median(daily_in[-56:] / mult[-56:]))
        expected = {d: level * day_multiplier(p, d, demo) for d in horizon}
        planted_date = demo + timedelta(days=PLANTED_DAY)

        suppliers = []
        for spec in p.suppliers:
            self.supplier_id += 1
            local = spec.aliases[2].split("@")[0]
            sup = dict(id=self.supplier_id, merchant_id=mid, name=spec.name, contact_name=spec.contact,
                       phone="+91" + str(int(rng.integers(7_000_000_000, 9_999_999_999))),
                       upi_vpa=f"{local}@{spec.aliases[2].split('@')[1]}", category=spec.category,
                       gstin=spec.gstin)
            self.rows["supplier"].append(sup)
            suppliers.append((spec, sup))

        def due_on(spec: SupplierSpec, d: date) -> bool:
            k = (d - planted_date).days
            if spec.cadence == "daily":
                return True
            if spec.cadence == "every2":
                return k % 2 == 0
            if spec.cadence == "every14":
                return k % 14 == 0
            if spec.cadence == "every20":
                return k % 20 == 0
            if spec.cadence.startswith("weekly:"):
                return d.weekday() == int(spec.cadence.split(":")[1])
            raise ValueError(spec.cadence)

        period = {"daily": 1, "every2": 2, "every14": 14, "every20": 20}
        invoice_counter: dict[int, int] = {}

        def add_payable(spec, sup, amount, d, status, paid_txn=None):
            self.payable_id += 1
            invoice_counter[sup["id"]] = invoice_counter.get(sup["id"], 0) + 1
            code = "".join(w[0] for w in spec.name.split()).upper()
            self.rows["payable"].append(dict(
                id=self.payable_id, merchant_id=mid, supplier_id=sup["id"], amount=int(amount),
                due_date=d, status=status, original_due_date=None,
                invoice_no=f"INV-{code}-{invoice_counter[sup['id']]:04d}", gst_rate=spec.gst_rate,
                paid_txn_id=paid_txn))

        # History: paid payables with an outflow transaction each.
        for di, d in enumerate(days):
            for spec, sup in suppliers:
                if not due_on(spec, d):
                    continue
                n = period.get(spec.cadence, 7)
                window = daily_in[max(0, di - n + 1): di + 1]
                base = spec.share * window.sum() * (n / max(len(window), 1))
                amount = max(200, int(round(base * math.exp(rng.normal(0, 0.1)) / 50) * 50))
                alias = spec.hard_alias if (spec.hard_alias and rng.random() < 0.04) else \
                    spec.aliases[int(rng.integers(0, len(spec.aliases)))]
                ts = datetime.combine(d, time(int(rng.integers(10, 16)), int(rng.integers(0, 60))))
                tid = self._add_txn(mid, ts, amount, "out", "supplier_payment", counterparty=alias,
                                    note=f"Payment to {spec.name}")
                add_payable(spec, sup, amount, d, "paid", tid)

        # Horizon: scheduled payables.
        def base_amount(spec: SupplierSpec, d: date) -> float:
            n = period.get(spec.cadence, 7)
            return max(200.0, spec.share * expected[d] * n)

        if p is RAMESH:
            targets = list(RAMESH_PRE_TARGETS)
            targets.append(p.buffer - RAMESH_BREACH_BELOW_BUFFER)
            while len(targets) < HORIZON_DAYS:
                targets.append(targets[-1] + RAMESH_RECOVERY_PER_DAY)
            prev = p.opening_balance
            for k, d in enumerate(horizon):
                total = prev + PESSIMISTIC_FACTOR * expected[d] - targets[k]
                due = [(s, sp) for s, sp in suppliers if due_on(s, d) and s.name != PLANTED_SUPPLIER]
                if d == planted_date:
                    planted = next((s, sp) for s, sp in suppliers if s.name == PLANTED_SUPPLIER)
                    add_payable(planted[0], planted[1], PLANTED_AMOUNT, d, "scheduled")
                    total -= PLANTED_AMOUNT
                total = max(total, 1_500)
                weights = np.array([base_amount(s, d) for s, _ in due])
                parts = total * weights / weights.sum()
                for (s, sp), amt in zip(due, parts):
                    add_payable(s, sp, max(100, int(round(amt / 50) * 50)), d, "scheduled")
                prev = targets[k]
        else:
            for d in horizon:
                for s, sp in suppliers:
                    if due_on(s, d):
                        amt = base_amount(s, d) * 0.9
                        add_payable(s, sp, max(100, int(round(amt / 50) * 50)), d, "scheduled")

    def _build_udhaar(self, mid: int, customers: list[dict]) -> None:
        by_first = {}
        for c in customers:
            by_first.setdefault(c["name"].split()[0], c)
        start = datetime.combine(self.demo, DEMO_START_TIME)
        entries = [(SUNITA[0], SUNITA[2], (next_friday(self.demo) - self.demo).days, 0)] + RAMESH_UDHAAR
        for first, amount, due_off, created_off in entries:
            c = by_first[first]
            self.udhaar_id += 1
            self.rows["udhaar"].append(dict(
                id=self.udhaar_id, merchant_id=mid, customer_id=c["id"], amount=amount,
                created_at=start + timedelta(days=created_off) - timedelta(minutes=30),
                due_date=self.demo + timedelta(days=due_off), status="open",
                settled_txn_id=None, note="", reminded_at=None))


def seed_all(engine: Engine, demo: date) -> dict[str, int]:
    """Drop and rebuild every table with deterministic synthetic data."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    b = Builder(demo)
    for mid, profile in enumerate(PROFILES, start=1):
        b.build_merchant(mid, profile)
    tables = {
        "merchant": models.Merchant, "settings": models.Settings, "customer": models.Customer,
        "supplier": models.Supplier, "transaction": models.Transaction,
        "payable": models.Payable, "udhaar": models.Udhaar,
    }
    with engine.begin() as conn:
        for name, model in tables.items():
            rows = b.rows[name]
            for i in range(0, len(rows), 5000):
                conn.execute(insert(model.__table__), rows[i:i + 5000])
    return {name: len(b.rows[name]) for name in tables}
