# MarketMemo — Your watchlist remembers what you missed

MarketMemo is a smart market watchlist. Its **Catch-Up** feature highlights meaningful changes that happened since the user last checked.

## GitHub Pages frontend

GitHub Pages hosts only the React frontend. Deploy the FastAPI backend and database first, then add a GitHub Actions repository secret named `VITE_API_BASE_URL` containing the public HTTPS backend URL (without a trailing slash). In the backend host, set `CORS_ORIGINS` to the exact GitHub Pages URL and set `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none`.

The workflow in `.github/workflows/deploy-pages.yml` builds and publishes the frontend whenever `main` is pushed. In the GitHub repository, open **Settings → Pages** and choose **GitHub Actions** as the source.

Step 3 adds persistent user baselines to the existing watchlist and Upstox quotes. A baseline is the last market state explicitly acknowledged by the user. It moves only when the user clicks **Mark caught up**; opening, refreshing, or loading market data does not change it.

Step 3 stores user state only. It does not yet determine whether anything meaningful happened after the baseline. A stock added after the user already has a baseline receives an initial baseline at its latest available price because the user has just seen that stock. Removing a stock also removes its baseline.

Step 4 adds deterministic Hidden Journey detection. For each stock baseline, the backend retrieves normalized Upstox V3 intraday/historical candles through the current time, finds the largest upward or downward excursion, and surfaces a Missed Moment only when the move was substantial but is mostly hidden by the current price. This is explanatory market context, not an investment recommendation.

Market Recap is separate from Catch-Up. It analyzes the latest NSE session in the available candle history, using the preceding session's final candle as its previous-close reference. Opening Market Recap never reads or updates user baselines. Significant session moves are classified as either `MOVED_THEN_REVERSED` or `MOVE_HELD`; quiet stocks are compressed into a count.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
pnpm install
```

If `pnpm` is unavailable, install Node.js and run `corepack enable` first.

Copy the environment example:

```bash
cp .env.example .env
```

Example:

```env
DATABASE_URL=sqlite:///./catchup.db
UPSTOX_ACCESS_TOKEN=your_upstox_access_token
MARKET_DATA_STALE_AFTER_SECONDS=120
INSTRUMENT_SEARCH_CACHE_SECONDS=300
HIDDEN_JOURNEY_MIN_EXCURSION=3.0
HIDDEN_JOURNEY_VISIBLE_RATIO=0.40
CATCHUP_CANDLE_MINUTES=5
MARKET_RECAP_MIN_EXCURSION_PCT=3.0
MARKET_RECAP_REVERSED_VISIBLE_RATIO=0.40
MARKET_RECAP_CANDLE_MINUTES=5
SUMMARY_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-3.1-flash-lite
```

Keep the real access token only in `.env`. That file is ignored by Git. Users search by company name or trading symbol and select an NSE stock; the backend obtains and stores the Upstox instrument key internally.

With `SUMMARY_PROVIDER=gemini`, Gemini rewrites verified Catch-Up and Market Recap facts into concise language. It never performs the market calculations. Responses are cached and checked for unsupported numbers and unsafe causal/advice language; any failure automatically uses the deterministic template. Keep `SUMMARY_PROVIDER=template` to disable external summary generation.

## Run

Backend terminal:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --app-dir backend --port 8000
```

Frontend terminal:

```bash
cd frontend
pnpm dev
```

Open <http://localhost:5173>. The data flow is:

```text
React → FastAPI → SQLite + Upstox quote API → FastAPI → React
```

`GET /watchlist` returns the saved stock data plus normalized quote fields: latest price, previous close, percentage change, day high/low, market timestamp and stale status. If Upstox fails for one stock, the rest of the watchlist still loads and that card shows a generic unavailable message.

`GET /stocks/search?q=infosys` searches Upstox instrument metadata for NSE equities and returns up to eight consumer-friendly matches. Search results are cached briefly; instrument keys are stored internally and are never shown in the form or stock cards.

`GET /catchup` analyzes each instrument from its own persisted baseline. The default product policy requires a maximum excursion of at least 3%, while the current return must be no more than 40% of that excursion. These thresholds are configured with `HIDDEN_JOURNEY_MIN_EXCURSION` and `HIDDEN_JOURNEY_VISIBLE_RATIO`; they are product choices, not universal financial rules.

`GET /market-recap` retrieves recent normalized candles, selects the newest session date present, and analyzes each watchlist stock relative to the preceding session close. During NSE hours it labels the session current; after hours, weekends, and holidays it labels the newest available date as the latest completed session.
