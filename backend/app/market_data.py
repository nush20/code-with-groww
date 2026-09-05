from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo
import httpx
from dotenv import load_dotenv


load_dotenv()

UPSTOX_QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"
UPSTOX_SEARCH_URL = "https://api.upstox.com/v2/instruments/search"
UPSTOX_CANDLES_URL = "https://api.upstox.com/v3/historical-candle"
NSE_TIMEZONE = ZoneInfo("Asia/Kolkata")
PROVIDER_ERROR = "Market data temporarily unavailable"
SEARCH_ERROR = "Stock search temporarily unavailable"
_search_cache: dict[str, tuple[float, list[dict]]] = {}
_quote_cache: dict[str, tuple[float, dict]] = {}
_candle_cache: dict[tuple[str, str, int, int], tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


class MarketDataError(RuntimeError):
    pass


def _upstox_get(url: str, *, params: dict | None = None) -> dict:
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise MarketDataError("Upstox access token is not configured")
    try:
        response = httpx.get(
            url,
            params=params,
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MarketDataError(PROVIDER_ERROR) from exc


def _normalized_candles(payload: dict) -> list[dict]:
    normalized = []
    for raw in (payload.get("data") or {}).get("candles") or []:
        if not isinstance(raw, list) or len(raw) < 6:
            continue
        try:
            normalized.append({
                "timestamp": _timestamp(raw[0]),
                "open": _number(raw[1], "open"),
                "high": _number(raw[2], "high"),
                "low": _number(raw[3], "low"),
                "close": _number(raw[4], "close"),
                "volume": int(raw[5]),
            })
        except (MarketDataError, TypeError, ValueError):
            continue
    return normalized


def fetch_intraday_candles(
    instrument_key: str,
    baseline_time: datetime,
    until: datetime | None = None,
) -> list[dict]:
    """Return chronological normalized candles strictly after the baseline."""
    baseline = baseline_time.replace(tzinfo=timezone.utc) if baseline_time.tzinfo is None else baseline_time.astimezone(timezone.utc)
    end = until or datetime.now(timezone.utc)
    encoded_key = quote(instrument_key, safe="")
    interval = int(os.getenv("CATCHUP_CANDLE_MINUTES", "5"))
    candles = []

    baseline_market_date = baseline.astimezone(NSE_TIMEZONE).date()
    end_market_date = end.astimezone(NSE_TIMEZONE).date()
    if baseline_market_date < end_market_date:
        historical_to = end_market_date.isoformat()
        historical_from = baseline_market_date.isoformat()
        candles.extend(_normalized_candles(_upstox_get(
            f"{UPSTOX_CANDLES_URL}/{encoded_key}/minutes/{interval}/{historical_to}/{historical_from}"
        )))

    candles.extend(_normalized_candles(_upstox_get(
        f"{UPSTOX_CANDLES_URL}/intraday/{encoded_key}/minutes/{interval}"
    )))

    unique = {candle["timestamp"]: candle for candle in candles}
    return sorted(
        (candle for candle in unique.values() if baseline < candle["timestamp"] <= end),
        key=lambda candle: candle["timestamp"],
    )


def fetch_recent_session_candles(
    instrument_key: str,
    until: datetime | None = None,
    lookback_days: int = 10,
) -> list[dict]:
    """Fetch enough normalized candles to find the latest and preceding NSE sessions."""
    end = until or datetime.now(timezone.utc)
    end_market_date = end.astimezone(NSE_TIMEZONE).date()
    from_market_date = end_market_date - timedelta(days=lookback_days)
    encoded_key = quote(instrument_key, safe="")
    interval = int(os.getenv("MARKET_RECAP_CANDLE_MINUTES", "5"))
    cache_key = (instrument_key, end_market_date.isoformat(), lookback_days, interval)
    cache_seconds = int(os.getenv("MARKET_CANDLE_CACHE_SECONDS", "60"))
    with _cache_lock:
        cached = _candle_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < cache_seconds:
        return cached[1]
    candles = []
    failures = 0

    # Keep minute-candle requests in bounded chunks. This supports the 1M
    # product window without relying on a single oversized provider request.
    urls = []
    chunk_end = end_market_date
    while chunk_end >= from_market_date:
        chunk_start = max(from_market_date, chunk_end - timedelta(days=27))
        urls.append(
            f"{UPSTOX_CANDLES_URL}/{encoded_key}/minutes/{interval}/{chunk_end.isoformat()}/{chunk_start.isoformat()}"
        )
        chunk_end = chunk_start - timedelta(days=1)
    urls.append(f"{UPSTOX_CANDLES_URL}/intraday/{encoded_key}/minutes/{interval}")
    for url in urls:
        try:
            candles.extend(_normalized_candles(_upstox_get(url)))
        except MarketDataError:
            failures += 1
    if failures == len(urls):
        raise MarketDataError(PROVIDER_ERROR)

    unique = {candle["timestamp"]: candle for candle in candles}
    result = sorted(unique.values(), key=lambda candle: candle["timestamp"])
    with _cache_lock:
        _candle_cache[cache_key] = (time.monotonic(), result)
    return result


def fetch_completed_daily_candles(
    instrument_key: str,
    before: datetime,
    sessions: int = 30,
) -> list[dict]:
    """Return daily candles ending before the personalized Catch-Up window.

    We deliberately end on the NSE date before the user's baseline date. This
    avoids allowing the evaluated journey to influence its own volatility
    baseline, at the cost of omitting a same-day completed session.
    """
    baseline = before.replace(tzinfo=timezone.utc) if before.tzinfo is None else before.astimezone(timezone.utc)
    to_date = baseline.astimezone(NSE_TIMEZONE).date() - timedelta(days=1)
    from_date = to_date - timedelta(days=max(45, sessions * 2))
    encoded_key = quote(instrument_key, safe="")
    payload = _upstox_get(
        f"{UPSTOX_CANDLES_URL}/{encoded_key}/days/1/{to_date.isoformat()}/{from_date.isoformat()}"
    )
    candles = _normalized_candles(payload)
    unique = {candle["timestamp"].astimezone(NSE_TIMEZONE).date(): candle for candle in candles}
    # N close-to-close returns require N+1 completed session closes.
    return sorted(unique.values(), key=lambda candle: candle["timestamp"])[-(sessions + 1):]


def search_stocks(query: str, limit: int = 8) -> list[dict]:
    """Search Upstox metadata and return only normalized NSE equity instruments."""
    normalized_query = " ".join(query.strip().split())[:50]
    if len(normalized_query) < 2:
        return []

    cache_seconds = int(os.getenv("INSTRUMENT_SEARCH_CACHE_SECONDS", "300"))
    cached = _search_cache.get(normalized_query.casefold())
    if cached and time.monotonic() - cached[0] < cache_seconds:
        return cached[1]

    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise MarketDataError("Upstox access token is not configured")

    try:
        response = httpx.get(
            UPSTOX_SEARCH_URL,
            params={
                "query": normalized_query,
                "exchanges": "NSE",
                "segments": "EQ",
                "instrument_types": "EQ",
                "page_number": 1,
                "records": min(limit, 10),
            },
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MarketDataError(SEARCH_ERROR) from exc

    results = []
    for raw in payload.get("data") or []:
        if raw.get("segment") != "NSE_EQ" or raw.get("instrument_type") != "EQ":
            continue
        symbol = raw.get("trading_symbol")
        instrument_key = raw.get("instrument_key")
        company_name = raw.get("short_name") or raw.get("name")
        if not all((symbol, instrument_key, company_name)):
            continue
        results.append({
            "symbol": str(symbol),
            "company_name": str(company_name).title(),
            "exchange": "NSE",
            "instrument_key": str(instrument_key),
        })
        if len(results) == limit:
            break

    _search_cache[normalized_query.casefold()] = (time.monotonic(), results)
    return results


def _number(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"Missing {field}") from exc


def _timestamp(value: Any) -> datetime:
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            parsed = datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError, OSError) as exc:
        raise MarketDataError("Invalid market timestamp") from exc


def fetch_latest_quote(instrument_key: str) -> dict:
    """Fetch and normalize one quote without exposing Upstox response details."""
    cache_seconds = int(os.getenv("MARKET_QUOTE_CACHE_SECONDS", "15"))
    with _cache_lock:
        cached = _quote_cache.get(instrument_key)
    if cached and time.monotonic() - cached[0] < cache_seconds:
        return cached[1]

    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise MarketDataError("Upstox access token is not configured")

    try:
        response = httpx.get(
            UPSTOX_QUOTE_URL,
            params={"instrument_key": instrument_key},
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MarketDataError(PROVIDER_ERROR) from exc

    quotes = payload.get("data") or {}
    if not quotes:
        raise MarketDataError(PROVIDER_ERROR)
    raw = next(iter(quotes.values()))
    ohlc = raw.get("ohlc") or {}
    price = _number(raw.get("last_price"), "latest price")
    previous_close = _number(ohlc.get("close"), "previous close")
    if previous_close <= 0:
        raise MarketDataError("Invalid previous close")
    day_high = _number(ohlc.get("high"), "day high")
    day_low = _number(ohlc.get("low"), "day low")
    market_timestamp = _timestamp(raw.get("last_trade_time") or raw.get("timestamp"))
    stale_after = int(os.getenv("MARKET_DATA_STALE_AFTER_SECONDS", "120"))
    age = max(0, (datetime.now(timezone.utc) - market_timestamp.astimezone(timezone.utc)).total_seconds())
    change_percent = ((price - previous_close) / previous_close) * 100

    result = {
        "price": round(price, 2),
        "previous_close": round(previous_close, 2),
        "change_percent": round(change_percent, 2),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "market_timestamp": market_timestamp,
        "is_stale": age > stale_after,
    }
    with _cache_lock:
        _quote_cache[instrument_key] = (time.monotonic(), result)
    return result
