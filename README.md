# MarketMemo

> **A smart market watchlist that remembers what happened while you weren't looking.**

MarketMemo is a full-stack Indian-market watchlist built for **Groww CODE 2026**. It combines persistent watchlists, real Upstox market data, daily market analysis, personal watch levels, company developments, and a baseline-based **Catch-Up engine** that detects meaningful events that may no longer be visible in the latest price.

Instead of only answering **“Where is this stock now?”**, MarketMemo also answers:

* **What happened during the trading day?**
* **What important movement happened while I was away?**
* **Did the stock cross a level I cared about?**
* **Was the movement unusual for this particular stock?**

The core market analysis is deterministic and explainable. MarketMemo does not use an LLM to calculate market movements, classify events, predict prices, or make investment recommendations.

> **Market state is shared. Meaning is personalized.**

---

## Problem Statement

Traditional watchlists primarily show the latest market snapshot.

That works when a user wants to know where a stock is **now**, but it can hide what happened between two visits.

Consider:

```text
₹100 → ₹102 → ₹106 → ₹110 → ₹105 → ₹101
```

A user who checks only the endpoints sees approximately:

```text
₹100 → ₹101
        +1%
```

But while they were away, the stock:

* moved 10% from the starting point,
* may have crossed a price level they cared about,
* and gave back most of the move before they returned.

The latest price no longer communicates that journey.

MarketMemo is built around this information gap.

Instead of treating a watchlist as a collection of current prices, it treats it as a **timeline with memory**.

---

## The Solution

MarketMemo separates the watchlist experience into three questions:

| View             | Question                                          |
| ---------------- | ------------------------------------------------- |
| **Watchlist**    | Where are my stocks now?                          |
| **Market Recap** | What happened during the latest trading session?  |
| **Catch-Up**     | What meaningful events happened while I was away? |

A fourth view, **Stock Detail**, exposes the underlying journey and calculations.

---

## 1. Smart Watchlist

Users can create a persistent personal watchlist of NSE equities.

Each stock shows:

* latest available price
* daily percentage change
* high and low
* previous close
* market-data timestamp and freshness

Stocks can be searched using company names or symbols; internal Upstox instrument identifiers remain an implementation detail.

Users can also attach a personal watch level when adding or inspecting a stock:

* fixed price above/below the current price
* percentage movement relative to a saved reference price

Watchlists and personal state persist across sessions after authentication.

---

## 2. Market Recap

**Market Recap answers: “What happened during the trading day?”**

Rather than ranking stocks only by closing return, MarketMemo reconstructs the price journey during the latest available trading session.

For watched stocks it can surface:

* session return
* period high and low
* largest excursion
* reversal or recovery
* largest watchlist movements
* sector-level activity
* relevant company developments published that day

This view is independent of the user's Catch-Up checkpoint.

It therefore remains useful after market hours or when the user has just marked themselves caught up.

### Company context

Relevant company developments are shown alongside market analysis when available.

They are treated as **context, not causality**.

MarketMemo may say:

> “A company development was also published during the session.”

It does not automatically say:

> “The stock moved because of this announcement.”

Price movement and company developments remain separate verified facts unless causality is explicitly established by a trusted source.

---

## 3. Catch-Up

**Catch-Up answers: “What important thing happened while I wasn't looking?”**

Each user has an explicit Catch-Up checkpoint.

When the user clicks **Mark caught up**, MarketMemo stores the acknowledged state. The next Catch-Up analyzes market observations after that checkpoint.

Opening the application, refreshing the page, or logging in does **not** silently move the checkpoint.

Catch-Up currently evaluates three independent signals.

### Hidden Journey

A **Hidden Journey** occurs when a stock makes a meaningful excursion from the user's checkpoint but later gives back enough of that movement that the current price hides much of what happened.

Example:

```text
LEFT                  PEAK                  NOW

₹100 ──────────────── ₹110 ─────────────── ₹101
                         │
                    +10% excursion

Current snapshot: +1%
Most of the journey is no longer visible.
```

The detector compares:

* checkpoint price
* highest and lowest observed prices
* latest price
* largest excursion
* reversal/recovery from that excursion

A movement is surfaced only when it satisfies the configured meaningful-change policy.

The threshold is a product policy, not a claim about whether a stock is fundamentally good or bad.

---

### Personal Watch Levels

Users can define levels they personally care about.

For example:

```text
Checkpoint       Watch level          Intraday high        Current

₹100 ─────────── ₹105 ─────────────── ₹110 ────────────── ₹101
                    ✓ crossed
```

MarketMemo remembers that the level was reached even if the current price later falls back below it.

The detector uses candle high/low observations rather than requiring the closing price to remain beyond the level.

A watch level therefore represents **personal relevance**, not a recommendation from MarketMemo.

---

### Unusual Movement

A 5% move does not mean the same thing for every stock.

MarketMemo therefore compares the observed excursion with the stock's own historical movement.

Historical daily returns are used to estimate typical daily movement.

For a multi-session Catch-Up interval:

```text
Expected movement
    =
Typical daily movement × √(trading-session equivalent)
```

The observed excursion is then compared with this expected movement:

```text
Significance multiple
    =
|Observed excursion| / Expected movement
```

For example:

```text
Observed excursion:     6.2%
Expected movement:      2.0%

Significance:           3.1× typical
```

This is a volatility-normalized comparison — **not a probability, confidence score, or prediction**.

If insufficient historical observations exist, MarketMemo reports that instead of fabricating a result.

---

## How Catch-Up Works

```text
User checkpoint
      │
      ▼
Upstox market observations
      │
      ▼
Normalized OHLC candles
      │
      ├───────────────┐
      │               │
      ▼               ▼
Hidden Journey    Watch Levels
      │               │
      └───────┬───────┘
              │
              ▼
      Unusual Movement
              │
              ▼
      Structured verified facts
              │
              ▼
       Summary Service
              │
              ▼
        Catch-Up card
```

A stock is surfaced if one or more meaningful-change detectors fire.

Quiet stocks are compressed rather than competing for the user's attention.

---

## Market Recap vs Catch-Up

These views intentionally solve different problems.

|                           | Market Recap                                     | Catch-Up                                  |
| ------------------------- | ------------------------------------------------ | ----------------------------------------- |
| **Question**              | What happened during the selected market period? | What happened while I was away?           |
| **Time window**           | 1D / standard market period                      | Since last acknowledged checkpoint        |
| **Personal baseline**     | No                                               | Yes                                       |
| **Personal watch levels** | Not required                                     | Yes                                       |
| **Purpose**               | Understand the market period                     | Recover information missed between visits |

This distinction also handles an important edge case.

If a user clicks **Mark caught up** after market close, there may correctly be nothing new in Catch-Up because no new market observations have occurred.

Market Recap can still explain what happened during the completed trading session.

---

## Deterministic by Design

MarketMemo does **not** ask an LLM to decide what happened in the market.

The analysis pipeline is:

```text
Market data
    ↓
Deterministic calculations
    ↓
Meaningful-change classification
    ↓
Structured verified facts
    ↓
User-facing language
```

Returns, excursions, reversals, recoveries, watch-level crossings, and unusual-movement calculations are performed in application code.

### Optional Gemini layer

Gemini is an optional wording layer.

When enabled, it receives only structured facts that have already been calculated and verified.

It is not allowed to:

* calculate or modify financial values
* classify meaningful changes
* infer unsupported causes
* predict future prices
* recommend trades
* introduce unsupported facts

Generated output is validated against the source facts.

If Gemini times out, fails, or produces unsupported output, MarketMemo falls back to deterministic templates.

> **AI explains verified facts; it does not decide what happened.**

---

## Data Reliability

Market applications need to communicate uncertainty rather than hide it.

MarketMemo therefore distinguishes:

```text
market_timestamp
```

The time represented by the market provider's observation.

from:

```text
received_at
```

The time MarketMemo received that observation.

Delayed or stale data remains labelled accordingly rather than being presented as live.

Provider failures are also isolated where possible. A failed quote, company-development request, or optional generated summary should not make the entire watchlist unusable.

---

## Reproducible Historical Replay

Live markets cannot be expected to produce a compelling event exactly when the application is being demonstrated.

MarketMemo therefore includes an isolated **historical replay**.

```text
HISTORICAL REPLAY · REAL MARKET DATA
```

The replay stores historical **inputs rather than calculated conclusions**, including:

* real historical OHLC candles
* historical observations required for unusual-movement analysis
* available company-development metadata
* replay checkpoint/watch-level state

The inputs are then passed through the **same production analysis pipeline** used by live Catch-Up.

Values such as:

* excursion percentage
* reversal/recovery percentage
* unusualness multiple
* detector results

are not stored as precomputed demo results.

The replay also never modifies:

* the user's live watchlist
* real watch levels
* real Catch-Up baseline

This makes the demonstration reproducible without maintaining a separate fake analysis implementation.

---

## Architecture

```text
                         ┌─────────────────┐
                         │   React + Vite  │
                         │     Frontend    │
                         └────────┬────────┘
                                  │
                             HTTPS / JSON
                                  │
                                  ▼
                         ┌─────────────────┐
                         │     FastAPI     │
                         │    + Pydantic   │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              │                   │                    │
              ▼                   ▼                    ▼
       ┌─────────────┐     ┌─────────────┐      ┌─────────────┐
       │ SQLAlchemy  │     │   Upstox    │      │   Gemini    │
       │             │     │             │      │  optional   │
       └──────┬──────┘     └─────────────┘      └─────────────┘
              │
              ▼
       ┌─────────────┐
       │ PostgreSQL  │
       │ production  │
       │             │
       │ SQLite      │
       │ local       │
       └─────────────┘
```

### Market state is shared; meaning is personalized

The number of user-watchlist entries can become much larger than the number of unique market instruments.

MarketMemo therefore separates:

**Shared market state**

* quotes
* candles
* historical movement
* company developments

from:

**Personal user state**

* watchlist membership
* personal watch levels
* Catch-Up checkpoints

Provider responses can be cached and reused rather than fetching identical market state independently for every user.

Personalized calculations are performed only where personalization is actually necessary.

---

## Key Engineering Decisions

### Explicit checkpoints

Catch-Up state moves only when the user explicitly clicks **Mark caught up**.

This prevents page refreshes or logins from silently destroying information about what happened while the user was away.

### Path over endpoints

MarketMemo analyzes the observations between two points rather than assuming the difference between the first and last price describes the entire journey.

### Explainable calculations

Every surfaced market event can be traced back to deterministic calculations and observed market data.

### Stock-relative significance

Unusual movement is normalized against the instrument's own historical behavior rather than applying the same percentage threshold to every stock.

### Graceful degradation

News, optional generated summaries, and individual provider requests are not required for the core market analysis to function.

### Context without invented causality

Company developments can help users understand what was happening during a period without MarketMemo automatically claiming that those developments caused the observed movement.

### Shared computation

Reusable instrument-level market state is separated from user-specific state to avoid unnecessary user × stock recomputation.

---

## Technology Stack

| Layer                   | Technology        |
| ----------------------- | ----------------- |
| Frontend                | React, Vite       |
| Backend                 | FastAPI, Pydantic |
| ORM                     | SQLAlchemy        |
| Production persistence  | PostgreSQL        |
| Local persistence       | SQLite            |
| Market data             | Upstox API        |
| Optional language layer | Gemini            |
| Frontend hosting        | GitHub Pages      |
| API / Database hosting  | Render            |

---

## Repository Structure

```text
backend/
├── app/                  # FastAPI routes, models, providers and analysis
├── tests/                # Unit and integration-style tests
└── requirements.txt

frontend/
├── src/                  # React application and components
└── package.json

.github/workflows/        # Deployment workflow
render.yaml               # Render deployment configuration
.env.example              # Safe configuration template
```

---

## Main API Endpoints

| Method   | Endpoint                  | Purpose                   |
| -------- | ------------------------- | ------------------------- |
| `GET`    | `/health`                 | API health                |
| `POST`   | `/auth/signup`            | Create account            |
| `POST`   | `/auth/login`             | Authenticate              |
| `POST`   | `/auth/logout`            | End session               |
| `GET`    | `/auth/me`                | Current user              |
| `GET`    | `/stocks/search`          | Search NSE equities       |
| `GET`    | `/watchlist`              | Watchlist + market state  |
| `POST`   | `/watchlist`              | Add instrument            |
| `DELETE` | `/watchlist/{id}`         | Remove instrument         |
| `GET`    | `/watch-levels`           | Personal watch levels     |
| `POST`   | `/watch-levels`           | Create watch level        |
| `DELETE` | `/watch-levels/{id}`      | Remove watch level        |
| `GET`    | `/market-recap`           | Watchlist market analysis |
| `GET`    | `/stocks/{symbol}/detail` | Period stock analysis     |
| `GET`    | `/catchup`                | Changes since checkpoint  |
| `POST`   | `/catchup/mark`           | Move checkpoint           |
| `GET`    | `/catchup/demo`           | Historical replay         |

---

## Run Locally

### Requirements

* Python 3.9+
* Node.js 20+
* pnpm
* Upstox access token
* PostgreSQL for a production-like environment, or SQLite for quick local development

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install -r backend/requirements.txt

cp .env.example .env
```

For SQLite:

```env
DATABASE_URL=sqlite:///./catchup.db
```

Configure the market provider:

```env
UPSTOX_ACCESS_TOKEN=your_token
SUMMARY_PROVIDER=template
```

Gemini is optional:

```env
SUMMARY_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL_NAME=gemini-3.1-flash-lite
```

Start the API:

```bash
python3 -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

Frontend configuration:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_BASE_PATH=/
```

Open:

```text
http://localhost:5173
```

---

## Testing

Backend:

```bash
source .venv/bin/activate
python3 -m pytest backend/tests
```

Frontend:

```bash
cd frontend
pnpm build
```

External providers are mocked in the normal automated test suite, so tests do not depend on live Upstox or Gemini availability.

---

## Deployment

The frontend is deployed using **GitHub Pages**.

The FastAPI backend and PostgreSQL database are configured for **Render** through `render.yaml`.

Production credentials such as:

* Upstox access tokens
* Gemini API keys
* database credentials

are stored as environment secrets and are never exposed to the frontend.

---

## Security

* Provider and database credentials remain backend-only.
* `.env` files are excluded from Git.
* Browser-visible `VITE_*` variables contain no secrets.
* Authentication state is server-managed.
* Production deployments use secure cookie configuration.
* Tokens accidentally exposed in logs, screenshots, commits, or conversations should be revoked immediately.

For a production financial application, additional controls such as email verification, password recovery, rate limiting, CSRF review, managed migrations, session-expiry policies, monitoring, and security review would be required.

---

## Prototype Limitations

MarketMemo is intentionally scoped as a prototype.

* It is not a trading terminal and does not guarantee real-time quotes.
* Company-development availability depends on the provider's available history.
* A development appearing during a market period does not establish causality.
* Watchlist-wide and sector summaries are not portfolio P&L.
* Historical data may be incomplete for newly listed or thinly covered instruments.
* Provider and summary caches are currently process-local.
* Sector fallback metadata is intentionally limited.
* Production deployment would require stronger observability, rate limiting, managed migrations, distributed caching where appropriate, and additional security controls.

---

## Design Principle

MarketMemo is built around one idea:

> **A current price tells you where a stock ended up. It doesn't always tell you what happened along the way.**

A useful watchlist should remember both.

---

## Disclaimer

MarketMemo is an information product and prototype. It does not provide investment advice, price predictions, trading recommendations, or guarantees about market outcomes.
