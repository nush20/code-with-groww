# MarketMemo

> **Your watchlist remembers what happened while you were away.**

MarketMemo is a smart Indian-market watchlist built for **Groww CODE 2026**. It combines real Upstox market data, persistent personal watchlists, price and percentage alerts, a watchlist-wide daily roundup, source-backed company developments, and a baseline-based **Catch-Up** experience.

Traditional watchlists show where a stock is now. MarketMemo also preserves the important journey between visits: an alert crossed and later reversed, a move that was unusually large for that stock, or a company development published during the period.

MarketMemo is an informational prototype. It does not predict prices, recommend trades, or provide investment advice.

---

## Live Demo

- **Web app:** [nush20.github.io/code-with-groww](https://nush20.github.io/code-with-groww/)
- **Backend:** [marketmemo-api.onrender.com](https://marketmemo-api.onrender.com)
- **Health check:** [marketmemo-api.onrender.com/health](https://marketmemo-api.onrender.com/health)

The backend uses Render's free tier, so its first request after inactivity may take around a minute while the service wakes up.

---

## Product Pitch

MarketMemo is a smart Indian-market watchlist that helps people understand what changed without watching prices all day. Users build a personal NSE watchlist, set price or percentage alerts, and see live market snapshots, daily watchlist impact, source-linked company developments, and clear stock journeys. Catch-Up remembers the user's last acknowledged checkpoint and surfaces important moves, reversals, unusual activity, and crossed alerts that a current price alone can hide. Upstox supplies market data and company news; deterministic code performs every financial calculation. Gemini may improve wording, but never decides signals. The result is a calm, personalized market brief—not another noisy trading terminal.

---

## Quickstart — No Docker Required

### Terminal 1: backend

```bash
git clone https://github.com/nush20/code-with-groww.git
cd code-with-groww

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt
cp .env.example .env

python3 -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

### Terminal 2: frontend

```bash
cd code-with-groww/frontend
npm install
cp .env.example .env
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

Before using live market features, place a valid Upstox access token in the root `.env`. Gemini is optional.

---

## Demo Walkthrough

1. Open MarketMemo and create an account.
2. Search for an NSE company by name, such as Reliance, Infosys, or Tata Steel.
3. Optionally add a fixed-price alert or an “up/down by X%” alert while adding the stock.
4. Add a few companies to build the watchlist.
5. Review the **Today in your watchlist** roundup for breadth, average direction, largest move, and development count.
6. Open **View today's activity** to see source-backed developments grouped by sector.
7. Select a stock to inspect its 1D, 1W, 2W, or 1M market journey and deterministic key facts.
8. Open **Catch me up** to see meaningful events since the saved checkpoint.
9. Use the historical replay when live markets do not naturally produce a strong demonstration event.
10. Mark the real Catch-Up as caught up to save a new personal checkpoint.

---

## The Core Problem

A normal watchlist is only a snapshot.

```text
₹100  →  ₹110  →  ₹101
left      peak      now
```

If someone leaves at ₹100 and returns at ₹101, the latest price shows only **+1%**. It hides the 10% rise and the reversal that happened in between.

MarketMemo changes the question from:

> Where is the stock now?

to:

> What mattered while I was away?

---

## Core Features

### 1. Personal, Persistent Watchlist

- Search NSE equities by company name or trading symbol.
- Keep the Upstox instrument key internal; users never need to enter it.
- Add and remove watched companies.
- Persist watchlists across refreshes and sessions.
- Keep each account's watchlist, alerts, and checkpoints separate.

### 2. Live Market Snapshot

Each watchlist company can show:

- latest available price
- daily percentage change
- session high and low
- previous close
- market observation time
- freshness status such as current, delayed, or stale

MarketMemo does not call delayed data “live” merely because it was recently fetched.

### 3. Daily Watchlist Roundup

The highlighted **Today in your watchlist** card explains the latest complete trading session across only the companies the user follows.

It includes:

- number of watched stocks higher, lower, or unchanged
- equal-weight average move across the watchlist
- largest watchlist move
- number of verified company developments
- expandable **View today's activity** feed

This is a watchlist-level directional summary—not portfolio P&L or an index calculation.

### 4. Company Developments and Daily Activity

MarketMemo fetches company developments from Upstox and keeps only items relevant to the watchlist and selected trading period.

The daily activity feed:

- groups developments by sector for larger watchlists
- preserves headline, publication time, source, and URL
- shows a short source-grounded summary when available
- links to the original article
- remains optional, so missing news never blocks market analysis

MarketMemo presents news as **relevant context**. It never automatically claims that an article caused a price move.

### 5. Stock Detail and Market Journey

Selecting a watchlist company opens its market journey for:

- **1D** — the full selected trading session
- **1W** — approximately five sessions
- **2W** — approximately ten sessions
- **1M** — approximately twenty-two sessions

The backend calculates period return, high, low, largest excursion, reversal or recovery, and important moments from normalized Upstox candles. The frontend renders these facts without recalculating them.

### 6. Price and Percentage Alerts

While adding a company, users can optionally choose:

- **Price alert:** above or below a target price
- **Percentage alert:** up or down by a selected percentage

Alerts stay visible on the watchlist. During Catch-Up, the production detector determines whether a level was actually crossed—even if the price later moved back.

### 7. Catch-Up With Memory

Catch-Up begins at the user's last explicitly acknowledged checkpoint.

Refreshing, opening the app, or logging in does not silently move the checkpoint. Only **Mark caught up** creates the next baseline.

For each watched company, Catch-Up can surface:

- a personal alert reached
- a meaningful move that later reversed
- a volatility-normalized unusual move
- a relevant company development during the same interval

Each company appears once even when several signals apply, and quiet companies are compressed to avoid clutter.

### 8. Hidden Journey Detection

A hidden journey is a meaningful excursion that is no longer obvious in the latest price.

```text
CHECKPOINT          EXTREME            LATEST
₹100 ────────────── ₹110 ───────────── ₹101
                     +10%               +1%
```

The detector uses the real checkpoint, candle extrema, latest value, and configured reversal threshold. Calculated results are not generated by an LLM.

### 9. Volatility-Normalized Unusual Movement

The same percentage move can be normal for one stock and unusual for another. MarketMemo compares the observed excursion with the company's own historical daily movement.

```text
expected movement = typical daily movement × √(trading sessions)

significance = |observed excursion| ÷ expected movement
```

This is a relative movement measure—not a probability, prediction, or confidence score. If history is insufficient, the system says so instead of fabricating a result.

### 10. Historical Replay Using Real Inputs

Live markets cannot be expected to produce an interesting event during a hackathon demo. MarketMemo therefore includes an isolated:

> **HISTORICAL REPLAY · REAL MARKET DATA**

Replay fixtures preserve historical Upstox candles and available development metadata. Those inputs pass through the same production detectors as live Catch-Up.

Fixtures do **not** store calculated excursion, reversal, unusualness, or detector conclusions. Replayed checkpoints and optional alerts represent scenario user state, and replay never changes the real user's watchlist, alerts, or checkpoint.

### 11. Optional Gemini Summary Layer

All financial facts and signal classifications are deterministic. Gemini receives only already-verified structured facts and may turn them into concise, less repetitive language.

Gemini does not:

- calculate prices, returns, reversals, or volatility
- choose which detector fires
- predict future prices
- recommend buying or selling
- add unsupported facts
- claim that news caused market movement

Generated text is validated. If Gemini times out, fails, or returns unsupported content, MarketMemo uses deterministic templates.

> **The model may explain the result. It never decides the result.**

### 12. Authentication and User Isolation

- Email/password signup and login
- Password hashing
- Server-side session records
- HTTP-only session cookie
- Persistent user-specific watchlists, alerts, and checkpoints
- Secure cross-site cookie configuration for GitHub Pages + Render deployment

---

## Daily Recap vs Catch-Up

These features deliberately answer different questions.

| | Daily watchlist / stock detail | Catch-Up |
|---|---|---|
| **Window** | Selected complete trading session or range | Since the user's saved checkpoint |
| **User baseline** | No | Yes |
| **Threshold required to display market facts** | No | Yes, for attention-worthy signals |
| **Purpose** | Understand the selected market period | Recover important events missed between checks |
| **News** | Same-day/period context | Context during the personalized interval |

After the market closes, a user may mark Catch-Up complete and correctly see no new Catch-Up events. The daily view can still explain that completed session.

---

## System Architecture

```text
┌──────────────────────────────┐
│ React + Vite                 │
│ Watchlist · Detail · Catch-Up│
└──────────────┬───────────────┘
               │ HTTPS / JSON + session cookie
               ▼
┌──────────────────────────────┐
│ FastAPI + Pydantic           │
│ Routes · validation · auth   │
└──────┬───────────┬───────────┘
       │           │
       ▼           ▼
┌─────────────┐  ┌────────────────────────────┐
│ SQLAlchemy  │  │ Upstox                    │
│ PostgreSQL  │  │ search · quotes · candles │
│ / SQLite    │  │ company developments      │
└─────────────┘  └─────────────┬──────────────┘
                               │ normalized observations
                               ▼
                 ┌────────────────────────────┐
                 │ Deterministic analysis     │
                 │ journey · alert · unusual  │
                 │ recap · watchlist impact   │
                 └─────────────┬──────────────┘
                               │ verified facts
                               ▼
                 ┌────────────────────────────┐
                 │ Template or Gemini wording │
                 └────────────────────────────┘
```

### Shared market state, personalized meaning

Quotes and candles are instrument-level observations. MarketMemo briefly caches these shared responses instead of fetching the same ticker separately for every user.

User-specific state remains separate:

- watchlist membership
- alert definitions
- Catch-Up checkpoint

```text
many users watch RELIANCE
          ↓
one cached market observation
          ↓
personal analysis against each user's state
```

---

## Reliability Principles

- **Honest freshness:** market timestamps and receipt times stay distinct.
- **No silent fake fallback:** provider failures are surfaced or handled as partial failures.
- **Partial results:** one failed quote or news request does not invalidate every company.
- **Optional context:** empty or unavailable news does not stop market calculations.
- **Insufficient history:** unusualness is unavailable rather than invented.
- **Validated summaries:** unsupported generated wording falls back to templates.
- **Explicit memory:** only user acknowledgement advances the Catch-Up checkpoint.
- **Source preservation:** development timestamps, publishers, and URLs remain attached.
- **No causality claims:** simultaneous news is context, not proof of why a price moved.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite |
| Backend | FastAPI, Pydantic |
| ORM | SQLAlchemy |
| Database | PostgreSQL in deployment, SQLite locally |
| Market data | Upstox API |
| Optional language layer | Gemini |
| Frontend hosting | GitHub Pages |
| Backend hosting | Render |

---

## Repository Structure

```text
code-with-groww/
├── backend/
│   ├── app/
│   │   ├── main.py                  API routes and orchestration
│   │   ├── auth.py                  Sessions and password handling
│   │   ├── database.py              SQLAlchemy configuration
│   │   ├── models.py                Persistent database models
│   │   ├── schemas.py               Pydantic API contracts
│   │   ├── market_data.py           Upstox search, quotes and candles
│   │   ├── market_recap.py          Range/session utilities
│   │   ├── change_detection.py      Deterministic detectors
│   │   ├── company_developments.py  News normalization and caching
│   │   ├── summary_service.py       Templates and optional Gemini
│   │   ├── demo_market_data.py      Isolated replay input loader
│   │   └── fixtures/                Historical replay inputs
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

---

## Local Configuration

Copy the example configuration:

```bash
cp .env.example .env
```

Minimal local configuration:

```env
DATABASE_URL=sqlite:///./catchup.db
UPSTOX_ACCESS_TOKEN=replace_with_your_token
SUMMARY_PROVIDER=template
```

To enable optional Gemini wording:

```env
SUMMARY_PROVIDER=gemini
GEMINI_API_KEY=replace_with_your_key
GEMINI_MODEL_NAME=gemini-3.1-flash-lite
```

Frontend configuration in `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_BASE_PATH=/
```

Never commit real API tokens. Production secrets belong in Render or GitHub repository secrets.

---

## PostgreSQL Setup

SQLite is the fastest local option. To test with PostgreSQL, create a database and replace `DATABASE_URL`:

```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/marketmemo
```

The deployed Render Blueprint creates PostgreSQL and injects its connection string automatically.

---

## Tests and Build

Backend tests:

```bash
source .venv/bin/activate
python3 -m pytest backend/tests -q
```

Frontend production build:

```bash
cd frontend
npm install
npm run build
```

Normal tests mock external providers and do not depend on live Upstox or Gemini availability.

---

## API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/auth/signup` | Create an account |
| `POST` | `/auth/login` | Start a session |
| `GET` | `/auth/me` | Return the current user |
| `POST` | `/auth/logout` | End the session |
| `GET` | `/stocks/search?q=` | Search normalized NSE equities |
| `GET` | `/watchlist` | Load the personal watchlist |
| `POST` | `/watchlist` | Add a selected company |
| `DELETE` | `/watchlist/{id}` | Remove a watched company |
| `GET` | `/watch-levels` | List personal alerts |
| `POST` | `/watch-levels` | Create a price or percentage alert |
| `DELETE` | `/watch-levels/{id}` | Remove an alert |
| `GET` | `/market-recap?range=1D` | Watchlist-wide recap and daily activity |
| `GET` | `/stocks/{symbol}/detail?range=1D` | Stock journey and market facts |
| `GET` | `/catchup/status` | Load checkpoint status |
| `GET` | `/catchup` | Analyze meaningful changes since checkpoint |
| `POST` | `/catchup/mark` | Save the next checkpoint |
| `GET` | `/catchup/demo` | Run isolated historical replay |

---

## Deployment

### Frontend — GitHub Pages

The workflow in `.github/workflows/deploy-pages.yml` builds and publishes the Vite frontend. Configure this repository secret:

```text
VITE_API_BASE_URL=https://marketmemo-api.onrender.com
```

In GitHub, set **Settings → Pages → Source** to **GitHub Actions**.

### Backend — Render

`render.yaml` provisions:

- the FastAPI web service
- a PostgreSQL database
- health checks
- production cookie and CORS configuration

Set these secret environment variables in Render:

```text
UPSTOX_ACCESS_TOKEN
GEMINI_API_KEY
```

`GEMINI_API_KEY` is only required when `SUMMARY_PROVIDER=gemini`.

---

## Prototype Limitations

- Upstox token availability and permissions determine which live data can be fetched.
- The Upstox news window may not retain older company developments.
- Render's free service may cold-start after inactivity.
- Shared caches are currently process-local rather than distributed.
- Watchlist-wide averages are not weighted by holdings and are not portfolio returns.
- Authentication is suitable for a prototype but production would need email verification, password reset, CSRF review, rate limiting, managed migrations, monitoring, and stronger operational controls.
- MarketMemo is not a licensed market-data terminal and does not guarantee real-time quotes.

---

## Engineering Principles

1. **Facts before wording** — calculations happen before any generated summary.
2. **Meaning over noise** — Catch-Up surfaces attention-worthy changes and compresses quiet stocks.
3. **Market state is shared; meaning is personal** — reuse observations, personalize analysis.
4. **Explicit memory** — the user's checkpoint moves only when they acknowledge it.
5. **Context is not causation** — news is linked and attributed without unsupported conclusions.
6. **Graceful degradation** — missing optional data never erases verified market facts.
7. **No trading advice** — the product explains observed history rather than predicting what to do next.

---

## Disclaimer

MarketMemo is a hackathon prototype and informational product. It does not provide investment advice, trading recommendations, price predictions, or guarantees about market outcomes.
