from __future__ import annotations

from datetime import date
from typing import Any

from .change_detection import analyze_market_session
from .market_data import NSE_TIMEZONE


RANGE_SESSIONS = {"1D": 1, "1W": 5, "2W": 10, "1M": 22}
RANGE_LOOKBACK_DAYS = {"1D": 10, "1W": 16, "2W": 25, "1M": 45}
RANGE_LABELS = {
    "1D": ("session", "latest session"),
    "1W": ("week", "last week"),
    "2W": ("two weeks", "last two weeks"),
    "1M": ("month", "last month"),
}
MEANINGFUL_MOVE_THRESHOLDS = {"1D": 3.0, "1W": 3.0, "2W": 3.0, "1M": 3.0}


def meaningful_move_threshold(range_name: str) -> float:
    """Allow independent tuning while preserving the current 3% policy."""
    import os

    fallback = os.getenv("MARKET_RECAP_MIN_EXCURSION_PCT", str(MEANINGFUL_MOVE_THRESHOLDS[range_name]))
    return float(os.getenv(f"MARKET_RECAP_MIN_EXCURSION_{range_name}_PCT", fallback))


def select_analysis_window(candles: list[dict[str, Any]], range_name: str) -> dict[str, Any] | None:
    """Select the last N real trading sessions plus their immediately preceding close."""
    by_date: dict[date, list[dict[str, Any]]] = {}
    for candle in candles:
        timestamp = candle.get("timestamp")
        if timestamp is not None:
            by_date.setdefault(timestamp.astimezone(NSE_TIMEZONE).date(), []).append(candle)
    dates = sorted(by_date)
    required = RANGE_SESSIONS[range_name]
    if len(dates) < 2:
        return None

    # Partial history is honest: use as many real sessions as Upstox returned,
    # while always reserving one preceding session for the reference close.
    selected_count = min(required, len(dates) - 1)
    selected_dates = dates[-selected_count:]
    reference_date = dates[-selected_count - 1]
    reference_candles = sorted(by_date[reference_date], key=lambda item: item["timestamp"])
    period_candles = sorted(
        [candle for day in selected_dates for candle in by_date[day]],
        key=lambda item: item["timestamp"],
    )
    if not reference_candles or not period_candles:
        return None
    return {
        "reference_price": reference_candles[-1]["close"],
        "reference_date": reference_date,
        "start_date": selected_dates[0],
        "end_date": selected_dates[-1],
        "session_count": selected_count,
        "is_partial": selected_count < required,
        "candles": period_candles,
    }


def analyze_period(candles: list[dict[str, Any]], range_name: str, minimum: float, visible_ratio: float) -> tuple[dict[str, Any], dict[str, Any]] | None:
    window = select_analysis_window(candles, range_name)
    if window is None:
        return None
    metrics = analyze_market_session(window["reference_price"], window["candles"], minimum, visible_ratio)
    if metrics["status"] != "ok":
        return None
    return window, metrics
