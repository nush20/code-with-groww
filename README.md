# MarketMemo

MarketMemo is a smart Indian-market watchlist that helps users understand what changed, what mattered, and what happened while they were away. It combines persistent watchlists, Upstox market data, personal alerts, daily market context, and a baseline-based **Catch-Up** experience.

> MarketMemo is a prototype and an information product. It does not predict prices or provide investment advice.

## Quick start

### Requirements

- Python 3.9 or newer
- Node.js 20 or newer
- pnpm
- A current Upstox access token

Clone the repository and install the backend:

```bash
git clone https://github.com/nush20/code-with-groww.git
cd code-with-groww
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt
cp .env.example .env
```

Open `.env`, keep SQLite for the simplest local setup, and add the Upstox token:

```env
DATABASE_URL=sqlite:///./catchup.db
UPSTOX_ACCESS_TOKEN=replace_with_your_current_token
SUMMARY_PROVIDER=template
GEMINI_API_KEY=
GEMINI_MODEL_NAME=gemini-3.1-flash-lite
```

Start the backend:

```bash
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

In a second terminal, install and start the frontend:

```bash
cd code-with-groww/frontend
pnpm install
cp .env.example .env
pnpm dev
```

The frontend `.env` should contain:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_BASE_PATH=/
```

Open [http://localhost:5173](http://localhost:5173). Confirm that the backend is running at [http://localhost:8000/health](http://localhost:8000/health).

If `pnpm` is unavailable, install Node.js LTS, reopen the terminal, and run `npm install --global pnpm`. Never commit `.env` or any real access token.

## What the product does

- Sign up or log in to access a personal watchlist.
- Search NSE equities by company name and add them to a persistent watchlist; symbols and Upstox instrument identifiers are resolved internally.
- View the latest available price, daily change, high, low, previous close, and data freshness.
- Add a personal alert while adding a stock:
  - a fixed price above or below the current price; or
  - a percentage move up or down from the saved reference price.
- Open a stock from the watchlist to see its 1D, 1W, 2W, or 1M market journey.
- Review the watchlist's latest-session activity, largest moves, sector picture, and relevant company developments.
- Use **Catch-Up** to see only meaningful events since the last checkpoint the user explicitly acknowledged.
- Run isolated historical replay examples without modifying live watchlists or user baselines.

## Product experiences

MarketMemo uses one central smart watchlist rather than a separate Market Recap screen. The watchlist contains current prices and the latest-session overview; clicking a company opens its detailed market journey.

| Experience | Time window | Personal baseline | Purpose |
| --- | --- | --- | --- |
| Watchlist | Current state and latest available session | No | Shows where watched stocks are now and what happened that day. |
| Stock detail | Selected 1D/1W/2W/1M period | No | Shows the selected company's complete market journey for that period. |
| Catch-Up | Since the user last clicked **Mark caught up** | Yes | Surfaces only events that meet the existing meaningful-change rules. |

Opening the app, refreshing a page, or logging in does not move the Catch-Up checkpoint. Only **Mark caught up** updates it. If the user returns after several days, Catch-Up analyzes the available observations across that longer interval.

## How Catch-Up works

For every watchlist stock, the backend loads the user's saved baseline and normalized Upstox candles after that checkpoint. The same deterministic pipeline evaluates:

- personal price or percentage-alert crossings;
- a meaningful move that later reversed and became less visible in the latest price;
- volatility-normalized unusual movement when enough history exists.

The calculations are performed in application code, not by an LLM. Company news may be shown as **Related development**, but MarketMemo does not claim that an article caused a price move.

If a user has no alert, Catch-Up can still surface a hidden journey or unusual movement. If nothing qualifies, it clearly reports that there were no meaningful changes.

Catch-Up provides two simple filters: **All** and **My alerts**. Market movements and related developments remain visible inside the relevant update instead of creating additional filter clutter. A company appears only once even when multiple signals apply.

## Data and summary rules

- Upstox supplies instrument metadata, quotes, candles, and company developments.
- The backend stores technical instrument keys; the frontend never asks users to enter or understand them.
- `market_timestamp` represents the provider's market observation time. `received_at` represents when MarketMemo received it.
- Delayed and stale labels are preserved instead of presenting old data as live.
- A failure for one quote or news request does not have to make the entire watchlist unusable.
- Watchlist and user state are stored in the database and therefore persist across browser sessions and devices after login.
- Shared provider responses are cached briefly so identical upstream data is not fetched independently for every user.
- Sector classification prefers provider metadata, uses one centralized fallback for known NSE symbols, and otherwise reports `Other`.

Gemini is optional. When enabled, it only rewrites already-verified deterministic facts into concise language. Generated text is validated against the source facts and cached; unsupported numbers, causal claims, advice, timeouts, or provider failures fall back to deterministic templates.

## Architecture

```text
React + Vite
    │ HTTPS / JSON
    ▼
FastAPI + Pydantic
    ├── SQLAlchemy ── PostgreSQL (production) / SQLite (local fallback)
    ├── Upstox ────── instruments, quotes, candles, developments
    └── Gemini ────── optional wording only
```

Market state is shared; meaning is personalized. Upstox observations and short-lived caches are reusable, while watchlists, alert levels, and Catch-Up baselines belong to an authenticated user.

## Technology

- Frontend: React, Vite
- Backend: FastAPI, Pydantic
- Persistence: SQLAlchemy with PostgreSQL; SQLite is supported for quick local development
- Market data: Upstox API
- Optional summaries: Gemini
- Hosting: GitHub Pages for the frontend and Render for the API/database

## Repository layout

```text
backend/
  app/                 FastAPI routes, models, providers, and analysis logic
  tests/               Backend unit and integration-style tests
  requirements.txt
frontend/
  src/                 React application and components
  package.json
.github/workflows/     GitHub Pages deployment
render.yaml            Render API and PostgreSQL blueprint
.env.example           Safe configuration template
```

## Run locally (without Docker)

### Prerequisites

- Python 3.9 or newer
- Node.js 20 or newer
- pnpm
- An Upstox access token for real market data
- PostgreSQL for a production-like setup; SQLite is sufficient for a quick local run

Do not paste lines beginning with `#` into the terminal. They are explanatory comments, not commands.

### 1. Backend setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt
cp .env.example .env
```

For the simplest local database, keep this in `.env`:

```env
DATABASE_URL=sqlite:///./catchup.db
```

For local PostgreSQL on macOS, one option is:

```bash
brew install postgresql@16
brew services start postgresql@16
createdb marketmemo
```

Then set a PostgreSQL URL appropriate for the local account:

```env
DATABASE_URL=postgresql+psycopg://localhost/marketmemo
```

### 2. Environment configuration

Add the real credentials only to `.env`:

```env
UPSTOX_ACCESS_TOKEN=replace_with_your_current_token
SUMMARY_PROVIDER=template
GEMINI_API_KEY=
GEMINI_MODEL_NAME=gemini-3.1-flash-lite
```

Use `SUMMARY_PROVIDER=template` to run without Gemini. To enable optional generated wording, set `SUMMARY_PROVIDER=gemini` and supply `GEMINI_API_KEY`.

The remaining detector, freshness, cache, and candle settings are documented in `.env.example`. The defaults are suitable for the prototype.

Start the API from the repository root:

```bash
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

Verify it at [http://localhost:8000/health](http://localhost:8000/health).

### 3. Frontend setup

Open a second terminal at the repository root:

```bash
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

The frontend environment should contain:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_BASE_PATH=/
```

Open [http://localhost:5173](http://localhost:5173).

If `pnpm`, `corepack`, or `node` is missing, install the current Node.js LTS release first, reopen the terminal, and run:

```bash
npm install --global pnpm
node --version
pnpm --version
```

## Typical product flow

1. Create an account or log in.
2. Search for an NSE company and click **Add**.
3. Optionally save a fixed-price or percentage alert.
4. Click a watchlist stock to inspect its market journey.
5. Open the highlighted daily activity to review the latest watchlist-wide session.
6. Click **Catch up** after time away.
7. Click **Mark caught up** only when the surfaced events have been reviewed.

The persistent request flow is:

```text
React → FastAPI → PostgreSQL → FastAPI → React
```

Market observations follow:

```text
React → FastAPI → cache/provider abstraction → Upstox → normalized models → React
```

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API health check |
| `POST` | `/auth/signup` | Create an account |
| `POST` | `/auth/login` | Start an authenticated session |
| `POST` | `/auth/logout` | End the session |
| `GET` | `/auth/me` | Return the current user |
| `GET` | `/stocks/search?q=...` | Search supported NSE equities |
| `GET` | `/watchlist` | Return the user's watchlist and normalized market data |
| `POST` | `/watchlist` | Add a selected instrument |
| `DELETE` | `/watchlist/{id}` | Remove a user's watchlist item |
| `GET` | `/watch-levels` | Return personal alerts |
| `POST` | `/watch-levels` | Add a price or percentage alert |
| `DELETE` | `/watch-levels/{id}` | Remove an alert |
| `GET` | `/market-recap` | Return latest-session watchlist analysis |
| `GET` | `/stocks/{symbol}/detail` | Return stock detail for the selected period |
| `GET` | `/catchup` | Analyze changes since the saved checkpoint |
| `POST` | `/catchup/mark` | Move the user's checkpoint explicitly |
| `GET` | `/catchup/demo` | Return isolated historical replay examples |

## Historical replay

Replay mode demonstrates Catch-Up with snapshotted historical Upstox inputs. The fixtures preserve real historical candles and available development metadata so the demo remains deterministic when upstream windows change. Calculated outputs are not stored: fixtures pass through the same production detectors used by live Catch-Up.

Replay does not modify the user's live watchlist, alerts, or baseline. Only the checkpoint and optional watch level are replayed user state, and the UI labels the experience **HISTORICAL REPLAY · REAL MARKET DATA**.

## Test and build

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

Unit tests mock external provider behavior; the normal test suite does not depend on live Upstox or Gemini availability.

## Deployment

### Backend and PostgreSQL on Render

The root `render.yaml` defines the FastAPI service and managed PostgreSQL database.

1. In Render, create a Blueprint from this repository.
2. Set `UPSTOX_ACCESS_TOKEN` and, only if used, `GEMINI_API_KEY` as secret environment variables.
3. Keep `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none` for the cross-site frontend/API session.
4. Set `CORS_ORIGINS=https://nush20.github.io` for the current GitHub Pages origin.
5. Copy the deployed HTTPS API URL.

Upstox access tokens may expire or be revoked. Replace the Render secret when required; never commit a token.

### Frontend on GitHub Pages

1. In the GitHub repository, open **Settings → Pages**.
2. Select **GitHub Actions** as the source.
3. Add the Actions secret `VITE_API_BASE_URL` with the public Render API URL, without a trailing slash.
4. Push to `main` or rerun the Pages workflow.

The workflow in `.github/workflows/deploy-pages.yml` builds the correct repository base path and publishes the frontend. The current site is expected at [https://nush20.github.io/code-with-groww/](https://nush20.github.io/code-with-groww/).

## Security

- Never put Upstox, Gemini, GitHub, or database credentials in frontend variables, source files, screenshots, commits, or this README.
- Only variables prefixed with `VITE_` are intended for the browser; assume they are public.
- Keep backend credentials in local `.env` files or hosting-provider secret settings.
- `.env` is ignored by Git, while `.env.example` contains placeholders only.
- Revoke and regenerate any token that has been pasted into chat, a terminal transcript, an issue, or a commit.
- Production authentication should add email verification, password recovery, rate limiting, CSRF review, session expiry controls, and managed schema migrations before handling real users.

## Prototype limitations

- It is not a trading terminal and does not guarantee real-time quotes.
- Watchlist-wide and sector figures are equal-weight summaries, not portfolio profit and loss.
- News availability depends on the Upstox response window and may be empty.
- Sector fallback coverage is intentionally limited; unknown companies remain `Other`.
- Provider and summary caches are currently process-local. A larger deployment should move shared cached observations and background ingestion to suitable managed infrastructure.
- The application currently creates/updates its prototype schema in application code. Production releases should use versioned database migrations.

## License

No project license file is currently included. Until the repository owner adds one, the source is not automatically licensed for redistribution or reuse.
