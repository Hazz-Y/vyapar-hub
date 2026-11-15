# Vyapar Hub · The AI Business Partner for Every Paytm Merchant

An AI business copilot for small Paytm merchants such as kirana stores and tea
stalls. The merchant speaks to it in Hindi or Hinglish, by voice or by typing, and
it answers through a simulated Paytm Soundbox. It warns before cash runs short, keeps the
udhaar (credit) book and collects on it, untangles supplier bills, and wins back customers
who have stopped coming. Nothing it suggests happens until the merchant approves it.

**Demo video:** https://youtu.be/MNR-UB9328s

**Live demo:** https://paytm-vypar-hub.vercel.app/?demo=1
(the `?demo=1` flag adds the presenter controls; the backend is on Render's free plan, so
the first request after a quiet spell can take about a minute while it wakes up)

Built by **Team Tensor** for the **Paytm Build for India AI Hackathon, Track 1**.

| Team Tensor |
| --- |
| Avishkar Jaiswal |
| Harsh Yadav |

## Problem Statement

> **Build the AI business partner for every Paytm merchant.**
>
> Build scalable AI-led solutions that help Paytm merchants grow their business, manage
> operations, and serve customers better. Think beyond payments, identify opportunities
> where AI can become a trusted business copilot for millions of merchants.

## The Problem

Paytm already sees every rupee a small merchant collects: each QR payment, each Soundbox
announcement. The merchant, though, still runs the business from memory and a paper
notebook. Three questions decide whether a kirana store has a good month, and today no
app answers them:

- **Will I have enough cash on the day the big supplier bill is due?** A ₹22,000
  wholesaler payment landing on a slow Friday can empty the till. The merchant finds out
  on Friday.
- **Who owes me money, and who should I remind today?** Udhaar is a large share of a
  neighbourhood shop's sales. Reminding a regular customer is socially awkward, so it
  doesn't happen and the credit goes stale.
- **Which regulars have quietly stopped coming?** A customer who used to visit three
  times a week and hasn't come for three weeks is visible in the payment data and
  invisible to the merchant.

A generic chatbot doesn't solve this. The users are busy, often more comfortable speaking
Hindi than typing English, and dealing with their own money. They need answers that are
**spoken**, **in their language**, **based on their own transactions**, and **never
wrong about a number**. Above all they need an assistant that **never moves money on its
own**. Those last two requirements drove most of the design decisions below.

## What Vyapar Hub Does

Five agents share one loop: **notice → suggest → merchant approves → act → confirm**.

| Agent | Notices | Suggests, and does once approved |
| --- | --- | --- |
| **Subah ki Report** | Yesterday's sales against a usual day for that weekday, today's bills, udhaar falling due | A spoken morning briefing on the Soundbox at opening time |
| **Cash Radar** | A 14-day forecast of the end-of-day balance dropping below the merchant's safety buffer | Moving one supplier bill to the earliest safe date, with a before-and-after chart |
| **Supplier** | Upcoming bills; messy ledger names such as "M/S A.T. KNP" for Agarwal Traders | Pay or reschedule a bill; match ledger names to suppliers; export a GST-ready CSV |
| **Udhaar** | Credit spoken aloud ("Sunita ji ne 650 ka udhaar liya, Friday tak denge") and its due date | A polite reminder with a UPI pay link on the due date; closes the entry when the payment arrives |
| **Growth** | Regulars who have lapsed, peak hours, slow weekdays, festival-season lift | A one-tap win-back offer, sent only to customers who opted in |

Every money or message action is created as a **pending action**. The app reads it back
("Agarwal Traders ka ₹22,000 payment 20 Nov se 7 Dec ko karna hai. Sahi hai?") and runs it
only after the merchant enters a PIN. The PIN is a demo PIN (`1234`); the app never asks
for a real UPI PIN, and no real money moves.

### The 3-minute demo

Watch the recorded walkthrough at https://youtu.be/MNR-UB9328s, or open the live demo with `?demo=1` and press **Reset** first.

1. **Briefing.** Press **Briefing**. The morning report plays on the Soundbox: yesterday's
   ₹16,408 in sales, 3% above a usual Saturday, today's bills and dues.
2. **Cash Radar.** The Cash tab shows a shortfall on Friday, day 5: the balance could fall
   to about -₹7,600 against a ₹5,000 buffer, because of Agarwal Traders' ₹22,000 bill. Say
   or type *"Agarwal ka payment 7 tareekh ko kar do"*. The app reads the change back and
   asks for the PIN; enter `1234` and the chart redraws with the shortfall gone.
3. **Udhaar.** Say *"Sunita ji ne 650 ka udhaar liya, Friday tak denge"* and the entry is
   logged. Press **Jump to Friday**: the demo clock moves to Friday 10:00 and the
   scheduler sends Sunita a reminder with a UPI link, shown as an on-screen preview. Press
   **Sunita pays 650**: the Paytm tune plays, the Soundbox announces the payment, and her
   udhaar closes automatically.
4. **Growth.** The Growth tab shows *14 regulars haven't come in 3 weeks*, 8 of whom
   opted in to offers. One tap drafts a 10% win-back message; approve it.
5. **How I got this.** The desktop sidebar lists every tool call behind the last answer,
   with its arguments and raw result, so anyone can check where each number came from.

## Setup and Run Instructions

### Prerequisites

- Python **3.10**
- Node.js **22** (or 20.19 and later)
- Optional: a [Groq](https://console.groq.com) API key (free tier works) and a
  [Sarvam AI](https://www.sarvam.ai) API key. Without them the app still runs, using a
  rule-based Hindi/Hinglish parser and the browser's built-in speech.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

On first start the backend seeds the synthetic demo database: two merchants, 400 days of
history and about 116,000 transactions. This takes around 30 seconds.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/?demo=1.

### 3. Tests

```bash
cd backend && python -m pytest -q     # 111 tests
cd frontend && npm test               # 39 tests
```

GitHub Actions runs both suites and a production build on every push.

### Environment variables (`backend/.env`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | empty | LLM via Groq (`GROQ_MODEL`, default `openai/gpt-oss-120b`). Empty means rule-based mode |
| `SARVAM_API_KEY` | empty | Speech-to-text (Saaras v3) and text-to-speech (Bulbul v3). Empty means browser speech |
| `DEMO_PIN` | `1234` | The demo approval PIN |
| `DEMO_DATE` | today (IST) | Fix the demo to a date for a repeatable run |
| `CORS_ORIGINS` | localhost:5173 | Allowed frontend origins, comma separated |
| `ENABLE_SCHEDULER` | `true` | Background reminders, the morning briefing and model warm-up |
| `ENABLE_HARDWARE` | `false` | Mirror Soundbox announcements to an Arduino display over USB (local only) |

The frontend reads `VITE_API_URL` (default `http://localhost:8000`). Keys live only in
`backend/.env`, which is gitignored; only `.env.example` is committed.

### Deployment

The live demo runs as two services:

- **Backend on Render**, defined in `render.yaml`. Create it with New → Blueprint and set
  `GROQ_API_KEY`, `SARVAM_API_KEY` and `CORS_ORIGINS` in the dashboard. The SQLite demo
  database lives on the instance's disk and re-seeds on every boot, so no database service
  is needed.
- **Frontend on Vercel**, with the root directory set to `frontend` and `VITE_API_URL`
  pointing at the Render URL. `frontend/vercel.json` adds the rewrite that makes deep
  links such as `/cash` work.

## Approach and Architecture

### High-level flow

```
Merchant speaks Hindi / Hinglish            "Agarwal ka payment 7 tareekh ko kar do"
  |
  |  browser mic -> POST /voice/turn
  v
Sarvam Saaras v3 (codemix STT)              transcript, Hindi number words -> digits
  |
  v
Agent runner (FastAPI)                      Groq, OpenAI-compatible tool calling
  |   11 tools, at most 5 calls a turn      rule-based parser if the LLM is unavailable
  |
  |-- read tools ----> services             sales, LightGBM cash forecast, udhaar,
  |                                         suppliers, growth insights, briefing
  |-- draft tools ---> PendingAction        read-back text, nothing executed yet
  |
  v
Number guard                                every figure in the reply must appear in a
  |                                         tool result, or the reply is replaced
  v
Reply text + pending actions + tool trace
  |
  |  Sarvam Bulbul v3 (TTS) -> Soundbox     spoken reply, LED pulses while speaking
  v
Approval sheet in the app                   read-back, amount, recipient, demo PIN pad
  |
  |  POST /actions/{id}/approve  (PIN checked server side)
  v
Executor                                    demo transaction, reschedule, udhaar entry,
                                            message preview; Soundbox confirmation
```

Alongside the request path, an APScheduler job ticks every 30 seconds on a simulated demo
clock. It sends udhaar reminders at 10:00 on the due date and plays the morning briefing
at the shop's opening time.

### Key engineering decisions and trade-offs

**The LLM never produces a number.** Every figure the merchant hears comes from a tool:
balances from the forecast service, totals from SQL sums, dates from the date resolver.
The model only chooses which tools to call and phrases the reply. After it answers, a
number guard extracts every figure from the reply and checks it against the tool results
and the merchant's own message. If any figure is unaccounted for, the reply is thrown
away and replaced with the tools' own pre-written sentences. The "How I got this" panel
shows the same trace to the merchant. The cost is occasionally stiffer phrasing when the
guard steps in. The benefit is that the assistant cannot invent a balance, which for a
merchant's money is the one mistake that ends trust.

**Money and messages move only on approval, and the server enforces it.** Draft tools
can only create a `PendingAction` with a spoken read-back. Execution lives in a separate
executor, reachable only through `POST /actions/{id}/approve`. That endpoint compares the
PIN in constant time and locks the action after five wrong attempts. Supplier payments
and reschedules always need the PIN. Udhaar reminders and win-back messages can be
switched to automatic in Settings, because they move no money. Even then, the win-back
executor re-checks customer consent at send time.

**Forecast the balance, not just the sales, and plan for the bad case.** Cash Radar
trains LightGBM quantile models (p10, p50, p90) on each merchant's daily inflows and adds
the scheduled supplier bills, giving a 14-day end-of-day balance range. Shortfalls are
judged on the pessimistic p10 line, because a merchant needs to know about a bad Friday,
not an average one. Each shortfall comes with the earliest date to move its bill to that
keeps the p10 line above the buffer. We checked the model with a rolling-origin backtest
over the last 60 days: its mean absolute error is ₹3,438 a day, against ₹5,212 for the
"same day last week" rule a shopkeeper might use, a 34% improvement.

**Messy ledger names: fuzzy matching first, then the LLM.** Bank and UPI narrations name
the same supplier many ways ("M/S A.T. KNP", "S.D. MILK", "VA KNP DIST"). RapidFuzz
handles most of them cheaply. Only the names it can't place confidently are sent to the
LLM in one batch, and the LLM may answer only with supplier IDs that already exist. On
the demo ledger, 895 of 914 transactions match by fuzzy rules and the remaining 19 by the
LLM, with none left unmatched.

**Built for a Hindi-speaking shop counter.** Speech uses Sarvam's Saaras v3 in codemix
mode, which handles a sentence that switches between Hindi and English mid-way. Hindi
number words ("saat sau pachaas") are converted to digits before parsing. Replies are
rewritten for the ear before text-to-speech: "₹22,000" becomes "22,000 rupaye" and a UPI
ID becomes "UPI par". The warm voice round trip, from speech in to reply audio out, is
about 3 seconds.

**Every external service has a fallback, and the app says which mode it is in.** With
no Groq key, a rule-based parser handles the core Hindi and Hinglish commands. With no
Sarvam key, the browser's own speech synthesis reads the replies. Customer messages are
always on-screen previews; real WhatsApp sending is deliberately switched off. A status
bar shows the active mode for the AI, voice and messages at all times, so a degraded demo
never pretends to be the real thing.

**Deterministic synthetic data, and a demo clock that can jump.** The seeder builds
both merchants from a fixed random seed. Their patterns include weekday rhythms, month-end
salary spikes, festival lift from real 2024–2027 festival dates, lapsed regulars and a
planted Friday shortfall. `POST /demo/reset` restores the exact same state every time. The
clock is stored as a (demo time, real time) pair, so time keeps flowing during a pitch.
**Jump to Friday** moves it forward, fills the skipped days with seeded sales, settles
routine bills, and leaves Friday's own bills waiting for approval.

**Consent and privacy by construction.** Reminders go only to phone numbers the
merchant typed in. Win-back messages go only to customers with `opted_in = true`, and
the rest are counted and reported as skipped. Payer UPI IDs are stored as hashes, never
raw.

**The browser does no money maths.** Totals, gaps, percentages and day counts are
computed on the server and arrive ready to display; the UI only formats them. A frontend
test renders each page from real API responses captured from the seeded backend, so a
renamed field fails CI instead of failing on stage.

## Stack

| Layer | Choice |
| --- | --- |
| API | Python 3.10, FastAPI, Pydantic v2, Uvicorn |
| Data | SQLModel on SQLite in WAL mode, integer rupees throughout |
| Forecasting | LightGBM 4.7 quantile regression (p10/p50/p90), recursive multi-step, NumPy and pandas |
| Matching | RapidFuzz, plus a batched LLM pass restricted to known supplier IDs |
| LLM | Groq, `openai/gpt-oss-120b`, OpenAI-compatible tool calling; xAI Grok supported as an alternative |
| Speech | Sarvam AI: Saaras v3 speech-to-text (codemix, hi-IN), Bulbul v3 text-to-speech |
| Jobs | APScheduler on the simulated demo clock |
| Frontend | React 19, Vite 8, Tailwind CSS v4, React Router, Recharts |
| Hardware (optional) | Arduino Uno with a display over USB serial at 9600 baud, via pyserial |
| Tests | pytest (111 tests) and Vitest with Testing Library (39 tests), GitHub Actions CI |
| Hosting | Render (API) and Vercel (web app) |

## Validation Results

| Check | Result |
| --- | --- |
| Backend tests | 111 passing: forecast, date and number parsing, udhaar matching, executor and PIN rules, scheduler, agent loop with a fake LLM, voice with a fake Sarvam client, demo time travel |
| Frontend tests | 39 passing: formatting, API client, PIN pad auto-submit, demo controls, Cash Radar, every page rendered from real API data |
| Forecast backtest | MAE ₹3,438 vs ₹5,212 for the same-day-last-week baseline, 34% better, over 60 days |
| Ledger matching | 914 transactions, 35 distinct names: 895 fuzzy, 19 LLM, 0 unmatched |
| Demo script on production | All five steps run end to end on the live deployment in Groq + Sarvam mode, about 3 s per agent turn |

Synthetic dataset, per reset:

| Table | Rows |
| --- | --- |
| Merchants | 2: Ramesh Kirana Store (Kanpur, Hindi) and Lakshmi Tea Stall (Chennai, Tamil) |
| Transactions | 116,579 over 400 days |
| Customers | 800 |
| Suppliers / payables | 16 / 2,032 |
| Udhaar entries | 10, including Sunita Verma's ₹650 due on Friday |

## Repository Layout

```
backend/
  app/agent/       tools, system prompt, runner (LLM loop, rule-based fallback, number guard)
  app/services/    forecast, sales, udhaar, suppliers, matching, gst, insights, briefing,
                   speech, executor, messaging, payments, timetravel, hardware
  app/routers/     REST endpoints, one module per area
  app/scheduler.py reminders and morning briefing on the demo clock
  app/seed.py      deterministic synthetic data
  tests/           pytest suite
frontend/
  src/pages/       Home, Cash Radar, Udhaar, Suppliers, Growth, Settings
  src/components/  RadarChart, Heatmap, ApprovalSheet, AssistantPanel, Soundbox, ToolTrace, DemoBar
  src/context/     app state: API client, approval queue, Soundbox playback queue
render.yaml        Render Blueprint for the API
.github/workflows  CI
```

## Limitations and Next Steps

**All data is synthetic.** The app has not been run on a real merchant's transactions,
and nothing is connected to Paytm's production systems. The seeded patterns are designed
to be realistic, but the forecast accuracy above is measured on generated data.

**The forecast range is too narrow.** In the backtest only 50% of actual days fell inside
the p10–p90 band, where a well-calibrated band would hold about 80%. The p50 line beats
the baseline clearly, but the band understates uncertainty, so the "safe date" advice is
more confident than it should be. Calibrating the quantiles, for example with conformal
adjustment, comes first.

**Free-tier limits.** Groq's free tier allows 8,000 tokens a minute, so rapid-fire
questions can fall back to the rule-based parser. Render's free plan sleeps after 15 idle
minutes and re-seeds on wake. The SQLite database is single-instance and resets on every
restart, which suits a demo but not production.

**The Soundbox is simulated.** Announcements play in the browser. The optional Arduino
display works only when the backend runs on the same laptop, because a cloud server
cannot reach a USB port.

**Messages are previews only.** Reminders and offers are shown on screen, not sent.

### What would come next, in order

1. Connect to real Paytm merchant data through official APIs, starting with read-only
   transaction history.
2. Calibrate the forecast band and retrain per merchant on a schedule.
3. Drive the Arduino display from the deployed site through the browser's Web Serial API.
4. Send reminders and offers through a consented WhatsApp Business channel.
5. Add more languages (Tamil, Marathi, Bengali, Telugu) using Sarvam's language support.
6. Move from SQLite to Postgres so many merchants can share one service.

## Additional Notes

Every merchant, customer, phone number, UPI ID and rupee amount in this repository is
synthetic, generated by `backend/app/seed.py`. No real money moves anywhere, no real
messages are sent, and the app never asks for, stores or handles a real UPI PIN.

Paytm, the Paytm Soundbox and the Paytm logo belong to Paytm (One97 Communications). They
appear here only as part of a hackathon prototype built for the Paytm Build for India AI
Hackathon. This project is not an official Paytm product.

Festival dates in `backend/data/festivals.csv` cover 2024 to 2027 and are used only to
shape the synthetic sales.
