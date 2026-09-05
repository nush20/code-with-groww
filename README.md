# MarketMemo

> **A smart market watchlist that remembers what happened while you weren't looking.**

MarketMemo is a full-stack Indian-market watchlist built for **Groww CODE 2026**. It combines real Upstox market data, persistent watchlists, personal alerts, daily market context, and a baseline-based **Catch-Up** experience.

Traditional watchlists show where a stock is now. MarketMemo also captures what happened between visits — including meaningful moves that later reversed, personal levels that were crossed, and movements that were unusual for that stock.

MarketMemo is an information product and prototype. It does not predict prices, recommend trades, or provide investment advice.

## Product Pitch

MarketMemo is a smart Indian-market watchlist that helps people understand what changed without watching prices all day. Users build a personal NSE watchlist, set price or percentage alerts, and see live market snapshots, daily watchlist impact, source-linked company developments, and clear stock journeys. Catch-Up remembers the user’s last acknowledged checkpoint and surfaces important moves, reversals, unusual activity, and crossed alerts that a current price alone can hide. Upstox supplies market data and company news; deterministic code performs every financial calculation. Gemini may improve wording, but never decides signals. The result is a calm, personalized market brief—not another noisy trading terminal.

---

## Feature Overview

* **Account-based persistence:** sign up, log in, log out, and keep each user’s watchlist, alerts, and Catch-Up checkpoint separate.
* **Consumer-friendly stock search:** search NSE equities by company name or symbol; Upstox instrument keys remain internal.
* **Persistent watchlist:** add and remove companies, with state stored in PostgreSQL in deployment and SQLite available locally.
* **Market snapshots:** latest available price, daily percentage change, session high and low, previous close, and honest freshness labels.
* **Watchlist-wide daily roundup:** breadth across watched stocks, the largest move, an equal-weight directional summary, and development count for the latest session.
* **Daily activity card:** expands into source-backed developments for watchlist companies, grouped by sector to remain readable as the list grows.
* **Stock detail:** click a watchlist company to inspect its Upstox candle journey over 1D, 1W, 2W, or 1M.
* **Deterministic market recap:** period return, high, low, largest excursion, reversal/recovery, important moments, and a concise facts-based explanation.
* **Personal alerts:** create an optional fixed-price alert or an “up/down by X%” alert while adding a company; saved alerts remain visible on the watchlist.
* **Catch-Up with memory:** analyze only the interval since the user’s last explicitly acknowledged checkpoint.
* **Hidden-journey detection:** preserve a meaningful move even if much of it disappears before the user returns.
* **Volatility-normalized unusual movement:** compare an observed move with that stock’s own historical behavior rather than applying one percentage threshold to every company.
* **Contextual company news:** show Upstox headline, timestamp, source, short summary, and source URL without claiming the news caused a price move.
* **Quiet-state compression:** show each company once, combine applicable signals, and keep unchanged stocks from cluttering Catch-Up.
* **Historical replay:** demonstrate real historical Upstox inputs through the same production calculation pipeline without changing live user state.
* **Optional Gemini wording:** turn verified structured facts into concise language, with validation and deterministic fallback.
* **Resilient provider handling:** quotes, analysis, and pages continue to degrade clearly when news, history, Gemini, or individual market requests are unavailable.

---

## The Problem

A watchlist is usually a snapshot.

Consider a stock that moves:

```text
₹100 → ₹110 → ₹101
```

If a user checks at ₹100 and returns at ₹101, the latest snapshot shows only a **+1% change**.

But while they were away, the stock moved 10% and gave back most of that move.

That journey can matter even though it is no longer visible in the current price.

**MarketMemo gives the watchlist memory.**

---

## What MarketMemo Does

MarketMemo is organized around three experiences:

| Experience       | What it answers                                                 |
| ---------------- | --------------------------------------------------------------- |
| **Watchlist**    | Where are my stocks now, and what happened today?               |
| **Stock Detail** | What did this stock's journey look like over 1D / 1W / 2W / 1M? |
| **Catch-Up**     | What meaningful events happened since I last checked?           |

### Watchlist

Users can search NSE companies and maintain a persistent personal watchlist.

The watchlist shows:

* latest available price and daily change
* high, low and previous close
* market-data freshness
* latest-session activity
* largest watchlist moves
* sector-level context
* relevant company developments

Users can also create personal alerts based on a fixed price or percentage move.

### Daily Watchlist Roundup

The highlighted **Today in your watchlist** card summarizes the most recent complete trading session across only the companies the user follows. It shows:

* how many watched stocks finished higher, lower, or unchanged
* the equal-weight average move across the watchlist
* the largest watchlist move
* how many verified company developments were found

Its **View today’s activity** control opens a compact feed of developments grouped by sector. Each item keeps its original source and link. This is a watchlist summary—not a portfolio return, index calculation, or claim of news causality.

### Stock Detail

Selecting a company opens its complete market journey for **1D, 1W, 2W or 1M**.

The backend calculates the period return, high, low, largest excursion, and reversal or recovery from normalized market candles. The frontend displays these results without independently recalculating financial values.

### Catch-Up

Catch-Up starts from the last checkpoint the user explicitly acknowledged with **Mark caught up**.

Opening the app, refreshing, or logging in does not move this checkpoint.

For each watched stock, MarketMemo analyzes observations after the checkpoint and looks for three signals:

#### Hidden Journey

A meaningful price move occurred while the user was away, but much of it later reversed.

```text
LEFT              PEAK               NOW
₹100 ──────────── ₹110 ───────────── ₹101

                   +10%
                                     only +1% now
```

The endpoint looks quiet, but the journey was not.

#### Personal Alert

A price or percentage level selected by the user was crossed during the interval, even if the stock later moved back.

```text
₹100 ───── ₹105 ───── ₹110 ───── ₹101
             ✓
        alert reached
```

#### Unusual Movement

MarketMemo compares the observed excursion with the stock's own historical movement.

```text
expected movement = typical daily movement × √(trading sessions)

significance = |observed excursion| / expected movement
```

This allows the same percentage move to be interpreted differently for stocks with different historical volatility.

It is a relative movement measure — not a probability, confidence score, or prediction.

If there is not enough history, MarketMemo reports insufficient history instead of manufacturing a result.

A stock appears once even if multiple signals apply. Quiet stocks are compressed rather than competing for attention.

---

## Daily Context vs Catch-Up

These intentionally solve different problems.

|                       | Daily Watchlist                   | Catch-Up                                        |
| --------------------- | --------------------------------- | ----------------------------------------------- |
| **Window**            | Latest available trading session  | Since last acknowledged checkpoint              |
| **Personal baseline** | No                                | Yes                                             |
| **Purpose**           | Understand what happened that day | Recover meaningful events missed between visits |

This matters after market close.

If the user clicks **Mark caught up** after the session, Catch-Up may correctly have nothing new to report. The daily watchlist can still explain what happened during that completed session.

---

## Company Developments

MarketMemo uses Upstox company developments to add context to market activity.

For the daily view, developments are matched to the corresponding trading day and displayed alongside the company's market journey.

MarketMemo keeps **market movement and company context separate**.

It can say:

> A company development was published during the session.

It does not automatically claim:

> The development caused the stock to move.

A failed or empty news response never prevents the underlying market analysis from working.

---

## Deterministic Analysis

MarketMemo's financial analysis does not depend on an LLM.

```text
Upstox market data
        ↓
Normalized candles
        ↓
Deterministic calculations
        ↓
Meaningful-change detection
        ↓
Structured facts
        ↓
User-facing summary
```

Returns, excursions, reversals, recoveries, alert crossings, and unusual-movement calculations are performed in application code.

### Optional Gemini summaries

Gemini is an optional wording layer.

When enabled, it receives already-verified structured facts and converts them into concise language. It does not calculate market values, classify events, predict prices, provide advice, or infer unsupported causes.

If generated output is invalid or the provider fails, MarketMemo falls back to deterministic templates.

> **The model can explain the result. It does not decide the result.**

---

## Architecture

```text
React + Vite
      │
      │ HTTPS / JSON
      ▼
FastAPI + Pydantic
      │
      ├── SQLAlchemy ── PostgreSQL / SQLite
      │
      ├── Upstox ────── instruments, quotes, candles, developments
      │
      └── Gemini ────── optional summary wording
```

### Shared market state, personalized meaning

Market observations such as quotes and candles are instrument-level information and can be reused across users.

User-specific state is stored separately:

* watchlist membership
* personal alerts
* Catch-Up checkpoints

Shared provider responses are cached briefly instead of fetching identical upstream data independently for every user.

This keeps personalization where it is actually required without duplicating shared market work.

---

## Reliability and Edge Cases

MarketMemo is designed to degrade gracefully.

* **Explicit checkpoint:** only **Mark caught up** changes the Catch-Up baseline.
* **Freshness:** provider observation time is preserved separately from when MarketMemo received the data.
* **Stale data:** delayed observations remain labelled instead of being presented as live.
* **Partial provider failure:** one failed quote or development request does not invalidate the entire watchlist.
* **Missing history:** unusual movement is unavailable rather than estimated from insufficient observations.
* **Missing developments:** market analysis still works without company news.
* **LLM failure:** deterministic summaries remain available.

---

## Historical Replay

Live markets cannot be expected to produce an interesting Catch-Up event during a demonstration.

MarketMemo therefore includes an isolated:

> **HISTORICAL REPLAY · REAL MARKET DATA**

Replay fixtures preserve historical Upstox inputs and pass them through the **same production detectors** used by live Catch-Up.

The fixtures store inputs such as candles and available development metadata — not calculated conclusions such as excursion percentage, reversal percentage, or detector results.

The replayed checkpoint and optional alert represent user state for the scenario.

Historical replay never modifies the user's real:

* watchlist
* alerts
* Catch-Up checkpoint

This keeps the demo deterministic without maintaining separate fake analysis logic.

---

## Tech Stack

| Layer                  | Technology                      |
| ---------------------- | ------------------------------- |
| Frontend               | React, Vite                     |
| Backend                | FastAPI, Pydantic               |
| Persistence            | SQLAlchemy, PostgreSQL / SQLite |
| Market Data            | Upstox API                      |
| Optional Summary Layer | Gemini                          |
| Deployment             | GitHub Pages, Render            |

---

## Repository Structure

```text
backend/
  app/                 FastAPI routes, models, providers and analysis
  tests/               Backend tests
  requirements.txt

frontend/
  src/                 React application
  package.json

.github/workflows/     Deployment
render.yaml            Render configuration
.env.example           Environment configuration
```

---

## Run Locally

### Requirements

* Python 3.9+
* Node.js 20+
* pnpm
* Upstox access token

### Backend

```bash
git clone https://github.com/nush20/code-with-groww.git
cd code-with-groww

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt

cp .env.example .env
```

For the simplest local setup:

```env
DATABASE_URL=sqlite:///./catchup.db
UPSTOX_ACCESS_TOKEN=your_token
SUMMARY_PROVIDER=template
```

Start the API:

```bash
python3 -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

If pnpm is already installed, `pnpm install` and `pnpm dev` work as well.

Set:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_BASE_PATH=/
```

Open `http://localhost:5173`.

---

## Testing

Backend:

```bash
python3 -m pytest backend/tests
```

Frontend:

```bash
cd frontend
npm run build
```

External providers are mocked in the normal automated test suite, so tests do not depend on live Upstox or Gemini availability.

---

## Main API Endpoints

| Method                    | Endpoint                  | Purpose                          |
| ------------------------- | ------------------------- | -------------------------------- |
| `POST`                    | `/auth/signup`            | Create account                   |
| `POST`                    | `/auth/login`             | Authenticate                     |
| `GET`                     | `/stocks/search`          | Search NSE equities              |
| `GET` / `POST` / `DELETE` | `/watchlist`              | Manage watchlist                 |
| `GET` / `POST` / `DELETE` | `/watch-levels`           | Manage personal alerts           |
| `GET`                     | `/market-recap`           | Latest-session analysis          |
| `GET`                     | `/stocks/{symbol}/detail` | Stock-period analysis            |
| `GET`                     | `/catchup`                | Analyze changes since checkpoint |
| `POST`                    | `/catchup/mark`           | Update checkpoint                |
| `GET`                     | `/catchup/demo`           | Historical replay                |

---

## Prototype Limitations

* MarketMemo is not a trading terminal and does not guarantee real-time quotes.
* Company-development availability depends on Upstox's available history.
* Company developments are context, not proof of causality.
* Watchlist-wide and sector figures are not portfolio P&L.
* Shared caches are currently process-local.
* Production use would require additional authentication hardening, rate limiting, managed migrations, monitoring, and infrastructure scaling.

---

## Disclaimer

MarketMemo is a prototype and information product. It does not provide investment advice, trading recommendations, price predictions, or guarantees about market outcomes.
