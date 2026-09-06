import os
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .auth import DEMO_USER_ID, SESSION_COOKIE, active_user_id, hash_password, new_session, reset_request_user, session_user, set_request_user, verify_password
from .company_developments import CompanyDevelopmentError, company_development_service
from .demo_market_data import replay_examples, replay_inputs
from .models import AuthSession, User, UserBaseline, WatchLevel, WatchlistItem
from typing import Literal, Optional, Tuple

from .change_detection import analyze_hidden_journey, analyze_unusual_movement, detect_watch_levels, market_session_status
from .schemas import AuthLogin, AuthSignup, AuthUserOut, CatchupMarkOut, CatchupOut, CatchupStatusOut, DeleteResponse, MarketRecapOut, StockDetailOut, StockSearchResult, WatchLevelCreate, WatchLevelOut, WatchlistCreate, WatchlistItemOut
from .market_data import MarketDataError, NSE_TIMEZONE, PROVIDER_ERROR, SEARCH_ERROR, fetch_completed_daily_candles, fetch_intraday_candles, fetch_latest_quote, fetch_recent_session_candles, search_stocks
from .market_recap import RANGE_LABELS, RANGE_LOOKBACK_DAYS, analyze_period, meaningful_move_threshold
from .summary_service import classify_analysis, summary_service
from .sector_metadata import sector_for


app = FastAPI(title="MarketMemo API")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

PUBLIC_PATHS = {"/health", "/auth/signup", "/auth/login", "/auth/demo"}


@app.middleware("http")
async def authenticated_session(request: Request, call_next):
    # CORS preflight requests do not carry the user's session cookie. Let the
    # CORS middleware validate them; authentication still applies to the
    # subsequent GET/POST/DELETE request.
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
        return await call_next(request)
    # Let FastAPI return its normal validation response without exposing any
    # protected data when a recap range is invalid.
    if request.url.path == "/market-recap" and request.query_params.get("range", "1D") not in {"1D", "1W", "2W", "1M"}:
        return await call_next(request)
    db = SessionLocal()
    try:
        user_id = session_user(db, request.cookies.get(SESSION_COOKIE))
    finally:
        db.close()
    if user_id is None:
        return JSONResponse({"detail": "Please sign in"}, status_code=status.HTTP_401_UNAUTHORIZED)
    context_token = set_request_user(user_id)
    try:
        return await call_next(request)
    finally:
        reset_request_user(context_token)


def set_session_cookie(response: Response, raw_token: str) -> None:
    secure_cookie = os.getenv("COOKIE_SECURE", "false").casefold() == "true"
    same_site = os.getenv("COOKIE_SAMESITE", "lax").casefold()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"
    response.set_cookie(
        SESSION_COOKIE, raw_token, max_age=30 * 24 * 60 * 60,
        httponly=True, samesite=same_site, secure=secure_cookie,
    )


@app.post("/auth/signup", response_model=AuthUserOut, status_code=status.HTTP_201_CREATED)
def signup(body: AuthSignup, response: Response, db: Session = Depends(get_db)):
    user = User(id=str(uuid.uuid4()), name=body.name.strip(), email=body.email.casefold(), password_hash=hash_password(body.password))
    try:
        db.add(user)
        raw_token = new_session(db, user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
    set_session_cookie(response, raw_token)
    return {"id": user.id, "name": user.name, "email": user.email, "is_demo": False}


@app.post("/auth/login", response_model=AuthUserOut)
def login(body: AuthLogin, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().casefold()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    raw_token = new_session(db, user.id)
    db.commit()
    set_session_cookie(response, raw_token)
    return {"id": user.id, "name": user.name, "email": user.email, "is_demo": False}


@app.post("/auth/demo", response_model=AuthUserOut)
def demo_login(response: Response, db: Session = Depends(get_db)):
    raw_token = new_session(db, DEMO_USER_ID)
    db.commit()
    set_session_cookie(response, raw_token)
    return {"id": DEMO_USER_ID, "name": "Demo User", "email": "", "is_demo": True}


@app.get("/auth/me", response_model=AuthUserOut)
def auth_me(db: Session = Depends(get_db)):
    user_id = active_user_id()
    if user_id == DEMO_USER_ID:
        return {"id": DEMO_USER_ID, "name": "Demo User", "email": "", "is_demo": True}
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in")
    return {"id": user.id, "name": user.name, "email": user.email, "is_demo": False}


@app.post("/auth/logout", response_model=DeleteResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))
        db.commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Signed out"}


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    # Step 1 databases need this single additive column. A migration framework
    # can replace this compatibility step when the schema grows further.
    if "watchlist_items" in inspect(engine).get_table_names():
        columns = {column["name"] for column in inspect(engine).get_columns("watchlist_items")}
        if "instrument_key" not in columns:
            with engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE watchlist_items ADD COLUMN instrument_key VARCHAR(120)"
                ))
        if "sector" not in columns:
            with engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE watchlist_items ADD COLUMN sector VARCHAR(80) NOT NULL DEFAULT 'Other'"
                ))
    if "watch_levels" in inspect(engine).get_table_names():
        columns = {column["name"] for column in inspect(engine).get_columns("watch_levels")}
        additions = {
            "alert_type": "VARCHAR(12) NOT NULL DEFAULT 'PRICE'",
            "target_percent": "FLOAT",
            "reference_price": "FLOAT",
        }
        with engine.begin() as connection:
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE watch_levels ADD COLUMN {name} {definition}"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def utc_value(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def current_catchup_status(db: Session) -> dict:
    rows = db.execute(
        select(UserBaseline, WatchlistItem.symbol)
        .join(WatchlistItem, (
            (WatchlistItem.user_id == UserBaseline.user_id)
            & (WatchlistItem.instrument_key == UserBaseline.instrument_key)
        ))
        .where(UserBaseline.user_id == active_user_id())
        .order_by(UserBaseline.baseline_time)
    ).all()
    stocks = [{
        "instrument_key": baseline.instrument_key,
        "symbol": symbol,
        "baseline_price": baseline.baseline_price,
        "baseline_time": utc_value(baseline.baseline_time),
    } for baseline, symbol in rows]
    return {
        "last_caught_up_at": max((stock["baseline_time"] for stock in stocks), default=None),
        "stocks": stocks,
    }


@app.get("/catchup/status", response_model=CatchupStatusOut)
def get_catchup_status(db: Session = Depends(get_db)):
    try:
        return current_catchup_status(db)
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc


def build_catchup_event(
    item,
    baseline_price: float,
    baseline_time: datetime,
    latest: dict,
    candles: list[dict],
    daily_candles,
    levels: list,
) -> Tuple[Optional[dict], dict, Optional[dict]]:
    """Run the provider-independent production Catch-Up analysis pipeline."""
    analysis = analyze_hidden_journey(
        baseline_price,
        baseline_time,
        candles,
        latest["price"],
        float(os.getenv("HIDDEN_JOURNEY_MIN_EXCURSION", "3.0")),
        float(os.getenv("HIDDEN_JOURNEY_VISIBLE_RATIO", "0.40")),
    )
    if analysis["status"] == "insufficient_data":
        return None, analysis, None

    if callable(daily_candles):
        try:
            daily_candles = daily_candles()
        except MarketDataError:
            daily_candles = None

    if daily_candles is None:
        unusualness = {
            "observed_excursion_pct": round(abs(analysis["max_excursion_pct"]), 2),
            "typical_daily_movement_pct": None,
            "trading_session_equivalent": max(1, len({
                candle["timestamp"].astimezone(NSE_TIMEZONE).date() for candle in candles
            })),
            "expected_window_movement_pct": None,
            "significance_multiple": None,
            "state": "UNAVAILABLE",
            "history_sessions_used": 0,
        }
    else:
        unusualness = analyze_unusual_movement(
            analysis["max_excursion_pct"],
            daily_candles,
            candles,
            minimum_history_sessions=int(os.getenv("UNUSUAL_MOVEMENT_MIN_HISTORY_SESSIONS", "15")),
            unusual_multiple=float(os.getenv("UNUSUAL_MOVEMENT_MULTIPLE", "2.0")),
            volatility_epsilon=float(os.getenv("UNUSUAL_MOVEMENT_VOLATILITY_EPSILON", "0.0001")),
        )

    watch_level_events = detect_watch_levels(baseline_price, candles, latest["price"], levels)
    is_unusual = unusualness["state"] == "UNUSUAL_MOVE"
    if not analysis["is_hidden_journey"] and not watch_level_events and not is_unusual:
        return None, analysis, unusualness

    signal_count = int(analysis["is_hidden_journey"]) + int(bool(watch_level_events)) + int(is_unusual)
    if signal_count > 1:
        headline = f"{signal_count} things worth knowing"
    elif watch_level_events:
        headline = f"Reached your ₹{watch_level_events[0]['target_price']:,.2f} watch level"
    elif is_unusual:
        headline = "Unusual move while you were away"
    else:
        headline = "Missed moment"
    direction_word = "Rose" if analysis["excursion_direction"] == "up" else "Fell"
    reversal_sentence = (
        f"{analysis['reversal_pct']:.0f}% of the move reversed."
        if analysis["excursion_direction"] == "up"
        else f"{analysis['reversal_pct']:.0f}% of the decline recovered."
    )
    event = {
        "type": "catchup_journey",
        "instrument_key": item.instrument_key,
        "symbol": item.symbol,
        "company_name": item.company_name,
        "headline": headline,
        "summary": f"{direction_word} as much as {abs(analysis['max_excursion_pct']):.2f}% while you were away. {reversal_sentence}",
        "baseline": {"price": baseline_price, "time": baseline_time},
        "current": {
            "price": latest["price"],
            "time": latest["market_timestamp"],
            "return_pct": analysis["current_return_pct"],
        },
        "excursion": {
            "direction": analysis["excursion_direction"],
            "price": analysis["excursion_price"],
            "time": analysis["excursion_time"],
            "return_pct": analysis["max_excursion_pct"],
        },
        "reversal_pct": analysis["reversal_pct"],
        "is_hidden_journey": analysis["is_hidden_journey"],
        "unusualness": unusualness,
        "watch_level_events": watch_level_events,
        "context": {"status": "NONE", "company_developments": []},
        "data_freshness": {
            "market_timestamp": latest["market_timestamp"],
            "is_stale": latest["is_stale"],
        },
    }
    return event, analysis, unusualness


def catchup_summary(event: dict, developments: list[dict]) -> dict:
    """Give the existing summary boundary verified facts, never raw candles."""
    return summary_service.generate({
        "summary_kind": "catchup",
        "symbol": event["symbol"],
        "headline": event["headline"],
        "market_facts": {
            "direction": event["excursion"]["direction"],
            "max_excursion_pct": event["excursion"]["return_pct"],
            "reversal_pct": event["reversal_pct"],
            "latest_return_pct": event["current"]["return_pct"],
            "baseline_price": event["baseline"]["price"],
            "baseline_time": event["baseline"]["time"],
            "excursion_price": event["excursion"]["price"],
            "excursion_time": event["excursion"]["time"],
            "latest_price": event["current"]["price"],
            "latest_time": event["current"]["time"],
            "is_hidden_journey": event["is_hidden_journey"],
            "significance_multiple": event["unusualness"]["significance_multiple"]
                if event["unusualness"]["state"] == "UNUSUAL_MOVE" else None,
        },
        "personal_facts": {
            "watch_levels_reached": [level["target_price"] for level in event["watch_level_events"]],
        },
        "company_developments": developments,
    })


def enrich_catchup_context(event: dict, developments: list[dict], status_value: str) -> dict:
    event["context"] = {"status": status_value, "company_developments": developments}
    generated = catchup_summary(event, developments)
    event["headline"] = generated["headline"]
    event["summary"] = generated["summary"]
    return event


@app.get("/catchup", response_model=CatchupOut)
def get_catchup(db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            select(WatchlistItem, UserBaseline)
            .join(UserBaseline, (
                (UserBaseline.user_id == WatchlistItem.user_id)
                & (UserBaseline.instrument_key == WatchlistItem.instrument_key)
            ), isouter=True)
            .where(WatchlistItem.user_id == active_user_id())
        ).all()
        active_levels = list(db.scalars(select(WatchLevel).where(
            WatchLevel.user_id == active_user_id(),
            WatchLevel.active.is_(True),
        )))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc

    events = []
    quiet_count = 0
    insufficient_count = 0
    unavailable_count = 0
    unusualness_insufficient_count = 0
    unusualness_unavailable_count = 0
    baseline_times = []
    levels_by_instrument = {}
    for level in active_levels:
        levels_by_instrument.setdefault(level.instrument_key, []).append(level)

    for item, baseline in rows:
        if baseline is None or not item.instrument_key:
            insufficient_count += 1
            continue
        baseline_time = utc_value(baseline.baseline_time)
        baseline_times.append(baseline_time)
        try:
            latest = fetch_latest_quote(item.instrument_key)
            candles = fetch_intraday_candles(item.instrument_key, baseline_time)
        except MarketDataError:
            unavailable_count += 1
            continue

        event, analysis, unusualness = build_catchup_event(
            item,
            baseline.baseline_price,
            baseline_time,
            latest,
            candles,
            lambda: fetch_completed_daily_candles(
                item.instrument_key,
                baseline_time,
                int(os.getenv("VOLATILITY_HISTORY_SESSIONS", "30")),
            ),
            levels_by_instrument.get(item.instrument_key, []),
        )
        if analysis["status"] == "insufficient_data":
            insufficient_count += 1
            continue
        if unusualness["state"] == "INSUFFICIENT_HISTORY":
            unusualness_insufficient_count += 1
        elif unusualness["state"] == "UNAVAILABLE":
            unusualness_unavailable_count += 1
        if event is None:
            quiet_count += 1
        else:
            try:
                developments = company_development_service.get_developments(
                    item.instrument_key,
                    item.symbol,
                    baseline_time,
                    event["current"]["time"],
                )
                context_status = "AVAILABLE" if developments else "NONE"
            except CompanyDevelopmentError:
                developments = []
                context_status = "UNAVAILABLE"
            events.append(enrich_catchup_context(event, developments, context_status))

    return {
        "since": min(baseline_times, default=None),
        "meaningful_count": len(events),
        "quiet_count": quiet_count,
        "insufficient_count": insufficient_count,
        "unavailable_count": unavailable_count,
        "unusualness_insufficient_count": unusualness_insufficient_count,
        "unusualness_unavailable_count": unusualness_unavailable_count,
        "events": events,
    }


@app.get("/catchup/demo", response_model=CatchupOut)
def get_catchup_demo(scenario: Literal["combined", "hidden-reversal", "personal-level"] = "combined"):
    """Run an explicit, isolated replay through the production analysis pipeline."""
    replays = replay_examples() if scenario == "combined" else [replay_inputs(scenario)]
    events = []
    for replay in replays:
        event, _, _ = build_catchup_event(
            replay["item"],
            replay["baseline_price"],
            replay["baseline_time"],
            replay["latest"],
            replay["candles"],
            replay["daily_candles"],
            replay["levels"],
        )
        if event:
            enriched = enrich_catchup_context(
                event,
                replay["developments"],
                "AVAILABLE" if replay["developments"] else "NONE",
            )
            events.append(enriched)
    replay = replays[0]
    return {
        "mode": "demo",
        "since": replay["baseline_time"],
        "meaningful_count": len(events),
        "quiet_count": 0 if events else 1,
        "insufficient_count": 0,
        "unavailable_count": 0,
        "unusualness_insufficient_count": 0,
        "unusualness_unavailable_count": 0,
        "events": events,
        "demo": {
            "label": "HISTORICAL REPLAY · REAL MARKET DATA",
            "description": "Three Catch-Up examples use actual historical Upstox candles. Only each checkpoint and watch level are replayed user state.",
            "scenario": replay["scenario"],
            "path": [
                replay["baseline_price"],
                event["excursion"]["price"] if event else replay["latest"]["price"],
                replay["latest"]["price"],
            ],
        },
    }


def session_company_context(item: WatchlistItem, session_date) -> dict:
    """Return company developments published on the selected date in NSE time."""
    start = datetime.combine(session_date, time.min, tzinfo=NSE_TIMEZONE)
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    try:
        developments = company_development_service.get_developments(
            item.instrument_key, item.symbol, start, end,
        )
        return {"status": "AVAILABLE" if developments else "NONE", "company_developments": developments}
    except CompanyDevelopmentError:
        return {"status": "UNAVAILABLE", "company_developments": []}


def watchlist_developments_for_date(items: list, session_date) -> dict:
    """Combine and deduplicate all Upstox news mapped to the watchlist on one NSE date."""
    combined = {}
    unavailable_count = 0
    eligible = [item for item in items if item.instrument_key]
    for item in eligible:
        try:
            developments = company_development_service.get_developments_on_date(
                item.instrument_key, item.symbol, session_date, NSE_TIMEZONE,
            )
        except CompanyDevelopmentError:
            unavailable_count += 1
            continue
        for development in developments:
            key = development["source_url"] or development["headline"].casefold()
            if key not in combined:
                combined[key] = {
                    "id": development["id"],
                    "type": development["type"],
                    "headline": development["headline"],
                    "summary": development["summary"],
                    "published_at": development["published_at"],
                    "source_name": development["source_name"],
                    "source_url": development["source_url"],
                    "symbols": [],
                }
            if item.symbol not in combined[key]["symbols"]:
                combined[key]["symbols"].append(item.symbol)
    developments = sorted(combined.values(), key=lambda value: value["published_at"], reverse=True)
    for development in developments:
        development["symbols"].sort()
    if developments:
        status_value = "PARTIAL" if unavailable_count else "AVAILABLE"
    elif unavailable_count:
        status_value = "UNAVAILABLE" if unavailable_count == len(eligible) else "PARTIAL"
    else:
        status_value = "NONE"
    return {
        "status": status_value,
        "date": session_date,
        "developments": developments,
        "unavailable_count": unavailable_count,
    }


def semantic_summary(item: WatchlistItem, metrics: dict, range_name: str, session_state: str, threshold: float, has_development: bool = False) -> dict:
    semantic_state = classify_analysis(metrics, threshold)
    facts = {
        "symbol": item.symbol,
        "range": range_name,
        "period_return_pct": metrics["session_return_pct"],
        "max_excursion_pct": metrics["max_excursion_pct"],
        "direction": metrics["direction"],
        "reversal_pct": metrics["reversal_pct"],
        "move_reversed_pct": metrics["reversal_pct"] if metrics["direction"] == "up" else None,
        "recovery_pct": metrics["reversal_pct"] if metrics["direction"] == "down" else None,
        "semantic_state": semantic_state,
        "period_high": metrics["high"],
        "period_low": metrics["low"],
        "period_latest": metrics["current_or_close"],
        "high_time": metrics["high_time"],
        "low_time": metrics["low_time"],
        "latest_time": metrics["latest_time"],
        "session_state": session_state,
    }
    generated = summary_service.generate(facts)
    summary = generated["summary"]
    if range_name == "1D" and has_development:
        summary += " A company development was also published during the session."
    return {
        "semantic_state": semantic_state,
        "display_label": generated["headline"],
        "short_summary": generated["short_summary"],
        "summary": summary,
        "movement_label": "Move reversed" if metrics["direction"] == "up" else "Decline recovered",
        "session_state": session_state,
    }


def recap_story(item: WatchlistItem, metrics: dict, range_name: str, session_state: str, market_timestamp: datetime, is_stale: bool, threshold: float, context: Optional[dict] = None) -> dict:
    context = context or {"status": "NONE", "company_developments": []}
    semantic = semantic_summary(item, metrics, range_name, session_state, threshold, bool(context["company_developments"]))
    return {
        "instrument_key": item.instrument_key,
        "symbol": item.symbol,
        "company_name": item.company_name,
        "classification": semantic["semantic_state"],
        **{key: metrics[key] for key in (
            "reference_price", "open", "high", "low", "current_or_close",
            "high_time", "low_time", "latest_time", "session_return_pct",
            "max_excursion_pct", "reversal_pct", "direction",
        )},
        **semantic,
        "explanation": f"{semantic['movement_label']} {metrics['reversal_pct']:.0f}%",
        "freshness": {"market_timestamp": market_timestamp, "is_stale": is_stale},
        "context": context,
    }


@app.get("/market-recap", response_model=MarketRecapOut)
def get_market_recap(
    db: Session = Depends(get_db),
    range_name: Literal["1D", "1W", "2W", "1M"] = Query("1D", alias="range"),
):
    try:
        items = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == active_user_id())))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc

    now = datetime.now(timezone.utc)
    fetched = []
    unavailable_count = 0
    eligible = [item for item in items if item.instrument_key]
    unavailable_count += len(items) - len(eligible)
    # Candle requests are independent and shared market observations, so fetch
    # the watchlist concurrently instead of adding one provider wait per stock.
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(eligible)))) as executor:
        futures = {
            executor.submit(fetch_recent_session_candles, item.instrument_key, now, RANGE_LOOKBACK_DAYS[range_name]): item
            for item in eligible
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                candles = future.result()
                if candles:
                    fetched.append((item, candles))
                else:
                    unavailable_count += 1
            except MarketDataError:
                unavailable_count += 1
    item_order = {item.id: index for index, item in enumerate(items)}
    fetched.sort(key=lambda value: item_order[value[0].id])

    available_dates = [
        candle["timestamp"].astimezone(NSE_TIMEZONE).date()
        for _, candles in fetched for candle in candles
    ]
    if not available_dates:
        return {"range": range_name, "period": None, "session": None, "analyzed_count": 0, "stories": [], "quiet_count": 0, "unavailable_count": unavailable_count, "watchlist_impact": None, "market_overview": []}

    session_date = max(available_dates)
    market_now = now.astimezone(NSE_TIMEZONE)
    session_status, session_label = market_session_status(session_date, market_now)
    minimum_excursion = meaningful_move_threshold(range_name)
    reversed_ratio = float(os.getenv("MARKET_RECAP_REVERSED_VISIBLE_RATIO", "0.40"))
    stale_after = int(os.getenv("MARKET_DATA_STALE_AFTER_SECONDS", "120"))
    story_inputs = []
    quiet_count = 0
    analyzed_count = 0
    latest_timestamp = None
    period = None
    impact_rows = []

    for item, candles in fetched:
        analyzed = analyze_period(candles, range_name, minimum_excursion, reversed_ratio)
        if analyzed is None:
            unavailable_count += 1
            continue
        window, metrics = analyzed
        analyzed_count += 1
        impact_rows.append({
            "instrument_key": item.instrument_key,
            "symbol": item.symbol,
            "company_name": item.company_name,
            "sector": sector_for(item.symbol, item.sector),
            "return_pct": round(metrics["session_return_pct"], 2),
            "high": round(metrics["high"], 2),
            "low": round(metrics["low"], 2),
        })
        market_timestamp = metrics["latest_time"]
        latest_timestamp = max(latest_timestamp, market_timestamp) if latest_timestamp else market_timestamp
        if period is None or window["end_date"] > period["end_date"]:
            _, phrase = RANGE_LABELS[range_name]
            period = {
                "start_date": window["start_date"], "end_date": window["end_date"],
                "session_count": window["session_count"], "is_partial": window["is_partial"],
                "label": phrase.title(),
            }
        is_stale = (now - market_timestamp.astimezone(timezone.utc)).total_seconds() > stale_after
        stock_session_status, _ = market_session_status(window["end_date"], market_now)
        stock_session_state = "IN_PROGRESS" if stock_session_status == "current" else "COMPLETE"
        semantic_state = classify_analysis(metrics, minimum_excursion)
        if semantic_state == "QUIET":
            quiet_count += 1
        # Market Recap is a complete period view, so every stock with valid
        # observations is visible. Thresholds only classify the wording; they
        # do not decide whether a stock appears here.
        story_inputs.append((item, metrics, stock_session_state, market_timestamp, is_stale, window["end_date"]))

    # News lookup and optional language generation are independent per company.
    # Running them concurrently keeps one slow provider response from multiplying
    # the wait by the number of meaningful stocks.
    def build_story(values):
        item, metrics, stock_session_state, market_timestamp, is_stale, end_date = values
        context = session_company_context(item, end_date) if range_name == "1D" else None
        return recap_story(
            item, metrics, range_name, stock_session_state, market_timestamp,
            is_stale, minimum_excursion, context,
        )

    stories = []
    if story_inputs:
        with ThreadPoolExecutor(max_workers=min(6, len(story_inputs))) as executor:
            stories = list(executor.map(build_story, story_inputs))

    watchlist_impact = None
    if range_name == "1D" and impact_rows:
        positive = [row for row in impact_rows if row["return_pct"] > 0]
        negative = [row for row in impact_rows if row["return_pct"] < 0]
        watchlist_impact = {
            "average_return_pct": round(sum(row["return_pct"] for row in impact_rows) / len(impact_rows), 2),
            "up_count": len(positive),
            "down_count": len(negative),
            "flat_count": len(impact_rows) - len(positive) - len(negative),
            "analyzed_count": len(impact_rows),
            "largest_gainer": max(positive, key=lambda row: row["return_pct"], default=None),
            "largest_decliner": min(negative, key=lambda row: row["return_pct"], default=None),
        }

    return {
        "range": range_name,
        "period": period,
        "session": {
            "date": session_date,
            "status": session_status,
            "label": session_label,
            "updated_at": latest_timestamp,
        },
        "analyzed_count": analyzed_count,
        "stories": stories,
        "quiet_count": quiet_count,
        "unavailable_count": unavailable_count,
        "daily_developments": watchlist_developments_for_date(items, period["end_date"]) if range_name == "1D" and period else None,
        "watchlist_impact": watchlist_impact,
        "market_overview": impact_rows,
    }


@app.get("/stocks/{symbol}/detail", response_model=StockDetailOut)
def get_stock_detail(
    symbol: str,
    db: Session = Depends(get_db),
    range_name: Literal["1D", "1W", "2W", "1M"] = Query("1D", alias="range"),
):
    try:
        item = db.scalar(select(WatchlistItem).where(
            WatchlistItem.user_id == active_user_id(),
            WatchlistItem.symbol == symbol.strip().upper(),
        ))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    if item is None or not item.instrument_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock is not in your watchlist")

    now = datetime.now(timezone.utc)
    try:
        candles = fetch_recent_session_candles(item.instrument_key, now, RANGE_LOOKBACK_DAYS[range_name])
    except MarketDataError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, PROVIDER_ERROR) from exc
    minimum = meaningful_move_threshold(range_name)
    visible_ratio = float(os.getenv("MARKET_RECAP_REVERSED_VISIBLE_RATIO", "0.40"))
    analyzed = analyze_period(candles, range_name, minimum, visible_ratio)
    if analyzed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not enough historical market data for this period")
    window, metrics = analyzed
    stale_after = int(os.getenv("MARKET_DATA_STALE_AFTER_SECONDS", "120"))
    market_timestamp = metrics["latest_time"]
    is_stale = (now - market_timestamp.astimezone(timezone.utc)).total_seconds() > stale_after
    detail_status, _ = market_session_status(window["end_date"], now.astimezone(NSE_TIMEZONE))
    session_state = "IN_PROGRESS" if detail_status == "current" else "COMPLETE"
    context = session_company_context(item, window["end_date"]) if range_name == "1D" else {"status": "NONE", "company_developments": []}
    semantic = semantic_summary(item, metrics, range_name, session_state, minimum, bool(context["company_developments"]))
    _, phrase = RANGE_LABELS[range_name]
    return {
        "symbol": item.symbol, "company_name": item.company_name,
        "instrument_key": item.instrument_key, "range": range_name,
        "period": {
            "start_date": window["start_date"], "end_date": window["end_date"],
            "session_count": window["session_count"], "is_partial": window["is_partial"],
            "label": phrase.title(),
        },
        "classification": semantic["semantic_state"],
        **semantic,
        "reference_price": metrics["reference_price"], "latest_price": metrics["current_or_close"],
        "period_return_pct": metrics["session_return_pct"],
        "period_high": metrics["high"], "period_high_time": metrics["high_time"],
        "period_low": metrics["low"], "period_low_time": metrics["low_time"],
        "peak_return_pct": metrics["peak_return_pct"], "trough_return_pct": metrics["trough_return_pct"],
        "max_excursion_pct": metrics["max_excursion_pct"], "direction": metrics["direction"],
        "reversal_pct": metrics["reversal_pct"],
        "explanation": f"{semantic['movement_label']} {metrics['reversal_pct']:.0f}%",
        "freshness": {"market_timestamp": market_timestamp, "is_stale": is_stale},
        "candles": [{"timestamp": candle["timestamp"], "close": candle["close"]} for candle in window["candles"]],
        "context": context,
    }


@app.post("/catchup/mark", response_model=CatchupMarkOut)
def mark_caught_up(db: Session = Depends(get_db)):
    try:
        items = list(db.scalars(select(WatchlistItem).where(
            WatchlistItem.user_id == active_user_id()
        )))
        existing = {baseline.instrument_key: baseline for baseline in db.scalars(
            select(UserBaseline).where(UserBaseline.user_id == active_user_id())
        )}
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc

    acknowledged_at = datetime.now(timezone.utc)
    updates = []
    failed = []
    for item in items:
        if not item.instrument_key:
            failed.append({"symbol": item.symbol, "reason": PROVIDER_ERROR})
            continue
        try:
            quote = fetch_latest_quote(item.instrument_key)
            updates.append((item, quote["price"]))
        except MarketDataError:
            failed.append({"symbol": item.symbol, "reason": PROVIDER_ERROR})

    if items and not updates:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Couldn’t update your Catch-Up state")

    try:
        for item, price in updates:
            baseline = existing.get(item.instrument_key)
            if baseline is None:
                baseline = UserBaseline(
                    user_id=active_user_id(),
                    instrument_key=item.instrument_key,
                    baseline_price=price,
                    baseline_time=acknowledged_at,
                    created_at=acknowledged_at,
                    updated_at=acknowledged_at,
                )
                db.add(baseline)
            else:
                baseline.baseline_price = price
                baseline.baseline_time = acknowledged_at
                baseline.updated_at = acknowledged_at
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Couldn’t update your Catch-Up state") from exc

    return {
        "message": "Caught up with partial market data" if failed else "Caught up",
        "caught_up_at": acknowledged_at,
        "updated": len(updates),
        "failed": failed,
    }


@app.get("/stocks/search", response_model=list[StockSearchResult])
def find_stocks(q: str = ""):
    try:
        return search_stocks(q)
    except MarketDataError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SEARCH_ERROR) from exc


@app.get("/watch-levels", response_model=list[WatchLevelOut])
def list_watch_levels(db: Session = Depends(get_db)):
    try:
        return list(db.scalars(select(WatchLevel).where(
            WatchLevel.user_id == active_user_id(),
            WatchLevel.active.is_(True),
        ).order_by(WatchLevel.created_at)))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc


@app.get("/watch-levels/{instrument_key}", response_model=list[WatchLevelOut])
def list_stock_watch_levels(instrument_key: str, db: Session = Depends(get_db)):
    try:
        return list(db.scalars(select(WatchLevel).where(
            WatchLevel.user_id == active_user_id(),
            WatchLevel.instrument_key == instrument_key,
            WatchLevel.active.is_(True),
        ).order_by(WatchLevel.direction)))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc


@app.post("/watch-levels", response_model=WatchLevelOut, status_code=status.HTTP_201_CREATED)
def create_watch_level(body: WatchLevelCreate, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(
        WatchlistItem.user_id == active_user_id(),
        WatchlistItem.instrument_key == body.instrument_key,
    ))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock is not in your watchlist")
    target_price = body.target_price
    reference_price = None
    if body.alert_type == "PERCENT":
        try:
            reference_price = float(fetch_latest_quote(item.instrument_key)["price"])
        except (MarketDataError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Current price unavailable; percentage alert was not created") from exc
        multiplier = 1 + body.target_percent / 100 if body.direction == "ABOVE" else 1 - body.target_percent / 100
        target_price = round(reference_price * multiplier, 4)
        if target_price <= 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Percentage alert creates an invalid target price")
    now = datetime.now(timezone.utc)
    level = WatchLevel(
        user_id=active_user_id(), instrument_key=item.instrument_key, symbol=item.symbol,
        target_price=target_price, alert_type=body.alert_type,
        target_percent=body.target_percent if body.alert_type == "PERCENT" else None,
        reference_price=reference_price, direction=body.direction, active=True,
        created_at=now, updated_at=now,
    )
    try:
        db.add(level)
        db.commit()
        db.refresh(level)
        return level
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"An active {body.direction} level already exists for this stock") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc


@app.delete("/watch-levels/{level_id}", response_model=DeleteResponse)
def delete_watch_level(level_id: int, db: Session = Depends(get_db)):
    level = db.scalar(select(WatchLevel).where(
        WatchLevel.id == level_id,
        WatchLevel.user_id == active_user_id(),
    ))
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watch level not found")
    try:
        db.delete(level)
        db.commit()
        return {"message": "Watch level removed"}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc


@app.get("/watchlist", response_model=list[WatchlistItemOut])
def list_watchlist(db: Session = Depends(get_db)):
    try:
        items = list(db.scalars(select(WatchlistItem).where(
            WatchlistItem.user_id == active_user_id()
        ).order_by(WatchlistItem.created_at)))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    results = []
    for item in items:
        base = WatchlistItemOut.model_validate(item).model_dump()
        if not item.instrument_key:
            base["market_error"] = PROVIDER_ERROR
            results.append(base)
            continue
        try:
            base["market"] = fetch_latest_quote(item.instrument_key)
        except MarketDataError:
            base["market"] = None
            base["market_error"] = PROVIDER_ERROR
        results.append(base)
    return results


@app.post("/watchlist", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(body: WatchlistCreate, db: Session = Depends(get_db)):
    try:
        has_existing_baseline = db.scalar(select(UserBaseline.id).where(
            UserBaseline.user_id == active_user_id()
        ).limit(1)) is not None
        item = WatchlistItem(
            user_id=active_user_id(),
            symbol=body.symbol,
            company_name=body.company_name,
            instrument_key=body.instrument_key,
            sector=sector_for(body.symbol, body.sector),
        )
        db.add(item)
        db.flush()
        result = WatchlistItemOut.model_validate(item).model_dump()
        try:
            result["market"] = fetch_latest_quote(item.instrument_key)
            if has_existing_baseline:
                acknowledged_at = datetime.now(timezone.utc)
                db.add(UserBaseline(
                    user_id=active_user_id(),
                    instrument_key=item.instrument_key,
                    baseline_price=result["market"]["price"],
                    baseline_time=acknowledged_at,
                    created_at=acknowledged_at,
                    updated_at=acknowledged_at,
                ))
        except MarketDataError:
            result["market_error"] = PROVIDER_ERROR
        db.commit()
        db.refresh(item)
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock is already in your watchlist") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc


@app.delete("/watchlist/{item_id}", response_model=DeleteResponse)
def remove_from_watchlist(item_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(
        WatchlistItem.id == item_id,
        WatchlistItem.user_id == active_user_id(),
    ))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist item not found")
    try:
        if item.instrument_key:
            db.execute(delete(UserBaseline).where(
                UserBaseline.user_id == active_user_id(),
                UserBaseline.instrument_key == item.instrument_key,
            ))
            db.execute(delete(WatchLevel).where(
                WatchLevel.user_id == active_user_id(),
                WatchLevel.instrument_key == item.instrument_key,
            ))
        db.delete(item)
        db.commit()
        return {"message": "Stock removed from watchlist"}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
