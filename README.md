# MarketMemo

> **Understand your watchlist without watching the market all day.**

MarketMemo is a smart Indian-market watchlist built for **Groww CODE 2026**. It helps users understand what happened across the stocks they follow and what important events they may have missed while they were away.

It combines Upstox market data, personal alerts, source-linked company developments, and a checkpoint-based **Catch-Up** experience.

MarketMemo is an informational prototype and does not provide investment advice.

---

## The Problem

A normal watchlist is good at answering:

> **Where are my stocks now?**

But when an investor returns after not watching the market, the latest prices leave out two important parts of the story.

### What happened across my watchlist today?

Looking at individual prices makes it difficult to quickly understand:

- Did most of my watched stocks move higher or lower?
- Which stocks moved the most?
- Which sectors were strongest or weakest?
- What relevant company developments happened that day?

MarketMemo reconstructs the latest available trading session into **Today in your watchlist** — showing how the watchlist moved as a whole, which stocks and sectors stood out, and the **source-backed company developments published that day**.

### What happened while I was away that the current price no longer shows?

Consider:

```text
₹100  →  ₹110  →  ₹101
LEFT      PEAK      NOW
```

A normal watchlist shows **+1%**.

But the stock actually climbed **10%** before giving almost all of the move back. It may also have crossed a personal alert or moved unusually relative to its own history.

MarketMemo's **Catch-Up** remembers those events from the user's last acknowledged checkpoint.

> **A normal watchlist shows the endpoint. MarketMemo remembers what happened.**

---

## What MarketMemo Does

### Today in Your Watchlist

An on-demand recap of the latest available trading session across the user's watchlist:

- **watchlist direction** — higher / lower / unchanged counts and equal-weight return
- **standout movement** — largest gainer and decliner
- **sector activity** — which parts of the watchlist were strongest or weakest
- **today's company developments** — source-backed news and developments for watched companies

This gives the user one place to answer:

> **What happened to the stocks I care about today?**

The backend calculates verified stock-level returns. The frontend groups those returns by sector and derives the equal-weight sector display.

This is a watchlist-level summary, not portfolio P&L.

### Stock Detail

Each watched stock can be explored across:

- **1D** — latest trading session
- **1W** — ~5 trading sessions
- **2W** — ~10 trading sessions
- **1M** — ~22 trading sessions

MarketMemo calculates period return, high/low, largest excursion, reversal/recovery, and important moments.

For **1D**, it also shows company developments published on the selected trading date.

### Catch-Up

Catch-Up answers:

> **What mattered since I last checked?**

It starts from the user's **last explicitly acknowledged checkpoint**.

Opening, refreshing, or logging into the app does not move the checkpoint. Only **Mark caught up** creates the next baseline.

Catch-Up can surface:

- personal alerts reached
- Hidden Journeys
- volatility-normalized unusual movements
- company developments within the checkpoint interval

Quiet stocks are compressed, and a company appears once even when multiple signals apply.

---

## Hidden Journey

A Hidden Journey captures a meaningful movement that the current price no longer reveals.

```text
CHECKPOINT       EXTREME        LATEST
₹100 ────────── ₹110 ───────── ₹101
                  +10%            +1%
```

By default, it is surfaced when:

```text
|largest excursion| ≥ 3%

AND

|current return| ≤ |largest excursion| × 0.40
```

So a meaningful move occurred, but at least **60% of it disappeared** from the latest snapshot.

These thresholds are explicit product policy, not AI decisions.

---

## Personal Alerts

Users can create:

- fixed-price alerts above or below a target
- percentage alerts up or down from the price at creation

Alerts are evaluated across the **entire Catch-Up candle interval**, not just against the latest price.

```text
₹100 → ₹106 → ₹101
        ↑
  ₹105 alert reached
```

Even though the stock ends at ₹101, MarketMemo remembers that ₹105 was reached.

Exact touches count. If the baseline is already beyond a target, the price must first return to the non-triggered side before a later crossing is reported.

---

## Unusual Movement

A 4% move may be normal for one stock and unusual for another.

MarketMemo compares the observed excursion with the stock's own historical daily movement.

```text
typical daily movement
    = sample standard deviation
      of historical close-to-close returns

expected window movement
    = typical daily movement
      × √(trading-session equivalent)

significance multiple
    = |largest excursion|
      ÷ expected window movement
```

By default:

```text
significance multiple ≥ 2.0
```

is considered unusual, provided sufficient historical observations exist.

This is a relative movement measure — **not a probability, confidence score, prediction, or recommendation**.

If history is insufficient or unusable, MarketMemo reports unusualness as unavailable.

---

## Company Developments

Price movement tells the user **what happened**. Company developments add context about **what was happening around the companies they follow**.

MarketMemo retrieves source-backed developments and displays:

- headline
- summary
- publication time
- publisher
- original source

For the **Daily Roundup and 1D Stock Detail**, developments are matched to the selected trading date.

For **Catch-Up**, developments are matched to the user's personalized checkpoint interval.

```text
Daily Roundup → What was happening today?
Catch-Up      → What was happening while I was away?
```

> **Context is not causation.**

MarketMemo never automatically claims that a development caused a price movement. Missing developments also never block market analysis.

---

## How the Market Calculations Work

All stock-level calculations are performed on the backend using normalized chronological OHLC data and unrounded values internally.

### Period Return

The reference is the close immediately preceding the analysis window.

```text
period return (%)
    = (latest price − reference close)
      ÷ reference close × 100
```

### Largest Excursion

```text
upward excursion (%)
    = (period high − reference close)
      ÷ reference close × 100

downward excursion (%)
    = (period low − reference close)
      ÷ reference close × 100
```

Whichever has the greater absolute magnitude becomes the **largest excursion**.

### Reversal / Recovery

For an upward move:

```text
reversal (%)
    = (period high − latest price)
      ÷ (period high − reference close) × 100
```

For a downward move:

```text
recovery (%)
    = (latest price − period low)
      ÷ (reference close − period low) × 100
```

Values are bounded between **0% and 100%**.

### Daily Watchlist Return

For each stock:

```text
stock return (%)
    = (latest-session close − preceding close)
      ÷ preceding close × 100
```

The watchlist average is equal-weight:

```text
watchlist average
    = sum of analyzed stock returns
      ÷ number of analyzed stocks
```

The backend also determines higher/lower/unchanged counts and the largest gainer/decliner.

---

## Daily Roundup vs Catch-Up

| | Today in your watchlist | Catch-Up |
|---|---|---|
| **Question** | What happened today? | What mattered while I was away? |
| **Scope** | Entire watchlist | Personalized meaningful events |
| **Window** | Latest trading session | Since saved checkpoint |
| **Baseline** | No | Yes |
| **Alerts** | No | Yes |
| **Developments** | Same-session context | Checkpoint-interval context |

A user can mark themselves caught up after market close and have no new Catch-Up events while still using the Daily Roundup to understand the completed session.

---

## Historical Replay

Live markets cannot be expected to produce a compelling Catch-Up event during a demo.

MarketMemo therefore includes:

> **HISTORICAL REPLAY · REAL MARKET DATA**

Replay fixtures preserve normalized historical candles and available development metadata.

```text
Normalized historical market inputs
              ↓
same deterministic analysis
              ↓
Hidden Journey · Unusual Movement
Alert Detection · Company Context
```

Fixtures store **inputs, not calculated conclusions**. The same production detectors recalculate excursion, reversal, unusualness, and alert results.

Replay state is isolated and never modifies the user's real watchlist, alerts, or checkpoint.

---

## Deterministic First, AI Optional

Financial analysis does not depend on an LLM.

```text
Upstox observations
        ↓
normalized market data
        ↓
deterministic calculations
        ↓
verified structured facts
        ↓
template / optional Gemini wording
```

Gemini may improve the wording of already-verified facts.

It does **not** calculate returns, decide detector results, infer unsupported causes, predict prices, or recommend trades.

If Gemini is unavailable or its output fails validation, deterministic templates are used.

> **The model may explain the result. It never decides the result.**

---

## Architecture

```text
                 React + Vite
                      │
                      ▼
              FastAPI + Pydantic
                 │          │
                 ▼          ▼
        SQLAlchemy       Upstox
      PostgreSQL/SQLite     │
                            ▼
                  Deterministic Analysis
                  ├── Daily Recap
                  ├── Market Journey
                  ├── Hidden Journey
                  ├── Alerts
                  └── Unusual Movement
                            │
                            ▼
                    Verified Facts
                            │
                            ▼
                 Template / Gemini
```

### Scaling Principle

Market observations belong to an instrument, not to a user.

**Shared state:** quotes, candles, company developments.

**Personal state:** watchlist membership, alerts, Catch-Up checkpoint.

```text
many users watch the same stock
              ↓
shared cached market observation
              ↓
personal evaluation against each user's state
```

> **Market state is shared. Meaning is personalized.**

The prototype uses process-local caching rather than adding distributed infrastructure prematurely.

---

## Reliability & Edge Cases

MarketMemo explicitly handles:

- **stale/delayed data** — observation time is separate from retrieval time
- **partial provider failures** — one failed stock does not invalidate the whole watchlist
- **missing developments** — market analysis remains available
- **insufficient volatility history** — unusualness is reported as unavailable
- **ambiguous OHLC candles** — exact intra-candle ordering is not invented
- **Gemini failure** — deterministic templates remain available
- **checkpoint integrity** — opening or refreshing does not move the baseline
- **provider failure** — live mode never silently substitutes fictional market data

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite |
| Backend | FastAPI, Pydantic |
| ORM | SQLAlchemy |
| Database | PostgreSQL / SQLite |
| Market data | Upstox API |
| Company developments | Upstox |
| Optional language layer | Gemini |
| Hosting | GitHub Pages + Render |

---

## Project Structure

```text
code-with-groww/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── auth.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── market_data.py
│   │   ├── market_recap.py
│   │   ├── change_detection.py
│   │   ├── company_developments.py
│   │   ├── summary_service.py
│   │   ├── demo_market_data.py
│   │   └── fixtures/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   └── api.js
│   ├── package.json
│   └── vite.config.js
├── .github/workflows/deploy-pages.yml
├── .env.example
├── render.yaml
└── README.md
```

Historical Replay fixtures already contain normalized inputs, so they enter directly at the deterministic-analysis stage.

---

## Live Demo

**Web app:**  
https://nush20.github.io/code-with-groww/

**Backend:**  
https://marketmemo-api.onrender.com

The backend is hosted on Render's free tier, so the first request after inactivity may take up to approximately one minute.

---

## Demo Walkthrough

For the clearest view of MarketMemo's core experience:

1. **Create an account and build a watchlist**  
   Search for NSE companies and add a few stocks to follow.

2. **See Today in your watchlist**  
   The Daily Roundup reconstructs the latest available trading session, including overall direction, largest moves, sector activity, and source-backed company developments.

3. **Explore a stock's market journey**  
   Open a watched stock and switch between **1D, 1W, 2W, and 1M**. The **1D** view also shows company developments from that trading date.

4. **Set a personal alert**  
   Create a price or percentage alert. MarketMemo checks the entire missed interval, so the event remains visible even if the stock later moves back.

5. **Open Catch me up**  
   Catch-Up compares market activity with the last acknowledged checkpoint and surfaces alerts, Hidden Journeys, unusual movements, and relevant company context.

6. **Expand a Catch-Up event**  
   Inspect the checkpoint, extreme, latest price, why the event was surfaced, and any relevant source-backed developments.

7. **Try Historical Replay**  
   Use Historical Replay for a reproducible Catch-Up demonstration using preserved real market inputs and the same production detectors.

8. **Mark yourself caught up**  
   Select **Mark caught up** to explicitly save a new checkpoint for future Catch-Up analysis.

---

## Run Locally

```bash
git clone https://github.com/nush20/code-with-groww.git
cd code-with-groww

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt

cp .env.example .env
```

Add a valid Upstox access token:

```env
UPSTOX_ACCESS_TOKEN=replace_with_your_token
```

Start the backend:

```bash
python3 -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

Then start the frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open:

```text
http://localhost:5173
```

Gemini is optional. The application works with deterministic template summaries without a Gemini API key.

---

## Testing

Backend:

```bash
python3 -m pytest backend/tests -q
```

Frontend:

```bash
cd frontend
npm run build
```

Core tests cover market calculations, Catch-Up detectors, alert behavior, summary fallback, and API behavior.

---

## API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/auth/signup` | Create account |
| `POST` | `/auth/login` | Start session |
| `GET` | `/auth/me` | Current user |
| `POST` | `/auth/logout` | End session |
| `GET` | `/stocks/search?q=` | Search NSE stocks |
| `GET` | `/watchlist` | Load watchlist |
| `POST` | `/watchlist` | Add stock |
| `DELETE` | `/watchlist/{id}` | Remove stock |
| `GET` | `/watch-levels` | List alerts |
| `POST` | `/watch-levels` | Create alert |
| `DELETE` | `/watch-levels/{id}` | Remove alert |
| `GET` | `/market-recap?range=1D` | Watchlist recap |
| `GET` | `/stocks/{symbol}/detail?range=1D` | Stock journey / 1D context |
| `GET` | `/catchup/status` | Checkpoint status |
| `GET` | `/catchup` | Catch-Up analysis |
| `POST` | `/catchup/mark` | Save checkpoint |
| `GET` | `/catchup/demo` | Historical Replay |

---

## Prototype Limitations

- Upstox token availability and permissions affect live data access.
- Stock-detail developments are currently available only for **1D**.
- Historical development availability depends on the upstream provider.
- Render's free tier may cold-start after inactivity.
- Shared caches are process-local.
- Watchlist and sector averages are equal-weight, not portfolio returns.
- Sector summaries are frontend-derived from backend-verified returns.
- MarketMemo does not guarantee real-time quotes.

---

## Design Principles

**Facts before wording · Meaning over noise · Explicit memory · Context is not causation · Graceful degradation · No trading advice**

> **Market state is shared. Meaning is personalized.**


