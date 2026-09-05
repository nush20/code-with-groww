from __future__ import annotations

from datetime import date, datetime, time
from math import sqrt
from statistics import stdev
from typing import Any

from .market_data import NSE_TIMEZONE


def market_session_status(session_date: date, market_now: datetime) -> tuple[str, str]:
    is_current = (
        session_date == market_now.date()
        and market_now.weekday() < 5
        and time(9, 15) <= market_now.time().replace(tzinfo=None) < time(15, 30)
    )
    return ("current", "Current session") if is_current else ("completed", "Latest session")


def analyze_market_session(
    reference_price: float,
    candles: list[dict[str, Any]],
    min_excursion: float,
    reversed_visible_ratio: float,
) -> dict[str, Any]:
    """Classify any chronological candle window relative to its preceding close."""
    valid = [
        candle for candle in candles
        if all(isinstance(candle.get(field), (int, float)) for field in ("open", "high", "low", "close"))
        and isinstance(candle.get("timestamp"), datetime)
    ]
    if reference_price <= 0 or not valid:
        return {"status": "insufficient_data"}

    ordered = sorted(valid, key=lambda candle: candle["timestamp"])
    session_open = ordered[0]["open"]
    peak = max(ordered, key=lambda candle: candle["high"])
    trough = min(ordered, key=lambda candle: candle["low"])
    session_close = ordered[-1]["close"]
    session_return = ((session_close - reference_price) / reference_price) * 100
    peak_return = ((peak["high"] - reference_price) / reference_price) * 100
    trough_return = ((trough["low"] - reference_price) / reference_price) * 100

    if abs(peak_return) >= abs(trough_return):
        direction = "up"
        excursion_price = peak["high"]
        excursion_return = peak_return
        denominator = peak["high"] - reference_price
        reversal = ((peak["high"] - session_close) / denominator * 100) if denominator > 0 else 0.0
    else:
        direction = "down"
        excursion_price = trough["low"]
        excursion_return = trough_return
        denominator = reference_price - trough["low"]
        reversal = ((session_close - trough["low"]) / denominator * 100) if denominator > 0 else 0.0

    reversal = max(0.0, min(100.0, reversal))
    meaningful = abs(excursion_return) >= min_excursion
    # Reversal is measured from the excursion back toward (or through) the
    # reference. Crossing to the opposite side is therefore always reversed.
    reversed_move = reversal >= (1 - reversed_visible_ratio) * 100
    classification = "QUIET" if not meaningful else "MOVED_THEN_REVERSED" if reversed_move else "MOVE_HELD"

    return {
        "status": "ok",
        "classification": classification,
        "reference_price": round(reference_price, 2),
        "open": round(session_open, 2),
        "high": round(peak["high"], 2),
        "high_time": peak["timestamp"],
        "low": round(trough["low"], 2),
        "low_time": trough["timestamp"],
        "current_or_close": round(session_close, 2),
        "latest_time": ordered[-1]["timestamp"],
        "session_return_pct": round(session_return, 2),
        "peak_return_pct": round(peak_return, 2),
        "trough_return_pct": round(trough_return, 2),
        "max_excursion_pct": round(excursion_return, 2),
        "reversal_pct": round(reversal, 2),
        "direction": direction,
    }


def analyze_hidden_journey(
    baseline_price: float,
    baseline_time: datetime,
    candles: list[dict[str, Any]],
    current_price: float,
    min_excursion: float,
    visible_ratio: float,
) -> dict[str, Any]:
    """Analyze normalized candles without provider or database dependencies."""
    if baseline_price <= 0 or not candles:
        return {"status": "insufficient_data", "is_hidden_journey": False}

    ordered = sorted(
        (candle for candle in candles if candle["timestamp"] > baseline_time),
        key=lambda candle: candle["timestamp"],
    )
    if not ordered:
        return {"status": "insufficient_data", "is_hidden_journey": False}

    peak = max(ordered, key=lambda candle: candle["high"])
    trough = min(ordered, key=lambda candle: candle["low"])
    current_return = ((current_price - baseline_price) / baseline_price) * 100
    peak_return = ((peak["high"] - baseline_price) / baseline_price) * 100
    trough_return = ((trough["low"] - baseline_price) / baseline_price) * 100

    if abs(peak_return) >= abs(trough_return):
        direction = "up"
        excursion_price = peak["high"]
        excursion_time = peak["timestamp"]
        excursion_return = peak_return
        denominator = peak["high"] - baseline_price
        reversal = ((peak["high"] - current_price) / denominator * 100) if denominator > 0 else 0.0
    else:
        direction = "down"
        excursion_price = trough["low"]
        excursion_time = trough["timestamp"]
        excursion_return = trough_return
        denominator = baseline_price - trough["low"]
        reversal = ((current_price - trough["low"]) / denominator * 100) if denominator > 0 else 0.0

    reversal = max(0.0, min(100.0, reversal))
    hidden = (
        abs(excursion_return) >= min_excursion
        and abs(current_return) <= abs(excursion_return) * visible_ratio
    )
    return {
        "status": "meaningful" if hidden else "quiet",
        "current_return_pct": round(current_return, 2),
        "peak_price": round(peak["high"], 2),
        "peak_time": peak["timestamp"],
        "peak_return_pct": round(peak_return, 2),
        "trough_price": round(trough["low"], 2),
        "trough_time": trough["timestamp"],
        "trough_return_pct": round(trough_return, 2),
        "excursion_direction": direction,
        "excursion_price": round(excursion_price, 2),
        "excursion_time": excursion_time,
        "max_excursion_pct": round(excursion_return, 2),
        "reversal_pct": round(reversal, 2),
        "is_hidden_journey": hidden,
    }


def analyze_unusual_movement(
    max_excursion_pct: float,
    historical_daily_candles: list[dict[str, Any]],
    catchup_candles: list[dict[str, Any]],
    minimum_history_sessions: int = 15,
    unusual_multiple: float = 2.0,
    volatility_epsilon: float = 0.0001,
) -> dict[str, Any]:
    """Compare an existing Catch-Up excursion with pre-window daily volatility."""
    by_date = {}
    for candle in historical_daily_candles:
        timestamp = candle.get("timestamp")
        close = candle.get("close")
        if isinstance(timestamp, datetime) and isinstance(close, (int, float)) and close > 0:
            by_date[timestamp.astimezone(NSE_TIMEZONE).date()] = candle
    ordered = sorted(by_date.values(), key=lambda candle: candle["timestamp"])
    returns = [
        ((current["close"] - previous["close"]) / previous["close"]) * 100
        for previous, current in zip(ordered, ordered[1:])
        if previous["close"] > 0
    ]

    if len(returns) < minimum_history_sessions:
        return {
            "observed_excursion_pct": round(abs(max_excursion_pct), 2),
            "typical_daily_movement_pct": None,
            "trading_session_equivalent": max(1, len(_catchup_trading_dates(catchup_candles))),
            "expected_window_movement_pct": None,
            "significance_multiple": None,
            "state": "INSUFFICIENT_HISTORY",
            "history_sessions_used": len(returns),
        }

    typical = stdev(returns)
    session_equivalent = max(1, len(_catchup_trading_dates(catchup_candles)))
    if typical <= volatility_epsilon:
        return {
            "observed_excursion_pct": round(abs(max_excursion_pct), 2),
            "typical_daily_movement_pct": round(typical, 4),
            "trading_session_equivalent": session_equivalent,
            "expected_window_movement_pct": None,
            "significance_multiple": None,
            "state": "INSUFFICIENT_HISTORY",
            "history_sessions_used": len(returns),
        }

    expected = typical * sqrt(session_equivalent)
    multiple = abs(max_excursion_pct) / expected
    return {
        "observed_excursion_pct": round(abs(max_excursion_pct), 2),
        "typical_daily_movement_pct": round(typical, 4),
        "trading_session_equivalent": session_equivalent,
        "expected_window_movement_pct": round(expected, 4),
        "significance_multiple": round(multiple, 2),
        "state": "UNUSUAL_MOVE" if multiple >= unusual_multiple else "NORMAL_RANGE",
        "history_sessions_used": len(returns),
    }


def _catchup_trading_dates(candles: list[dict[str, Any]]) -> set[date]:
    return {
        candle["timestamp"].astimezone(NSE_TIMEZONE).date()
        for candle in candles
        if isinstance(candle.get("timestamp"), datetime)
    }


def detect_watch_levels(
    baseline_price: float,
    candles: list[dict[str, Any]],
    latest_price: float,
    levels: list[Any],
) -> list[dict[str, Any]]:
    """Detect one retrospective reach per active level from normalized OHLC candles."""
    valid = sorted((
        candle for candle in candles
        if isinstance(candle.get("timestamp"), datetime)
        and all(isinstance(candle.get(field), (int, float)) for field in ("high", "low"))
    ), key=lambda candle: candle["timestamp"])
    events = []
    for level in levels:
        if not getattr(level, "active", True):
            continue
        target = float(level.target_price)
        direction = str(level.direction).upper()
        armed = baseline_price < target if direction == "ABOVE" else baseline_price > target
        reached_index = None

        for index, candle in enumerate(valid):
            if not armed:
                moved_to_safe_side = candle["low"] < target if direction == "ABOVE" else candle["high"] > target
                if moved_to_safe_side:
                    # OHLC does not reveal whether high or low occurred first.
                    # Arm here and require a later candle for an honest re-cross.
                    armed = True
                continue
            reached = candle["high"] >= target if direction == "ABOVE" else candle["low"] <= target
            if reached:
                reached_index = index
                break

        if reached_index is None:
            continue
        event_candle = valid[reached_index]
        after_reach = valid[reached_index:]
        currently_beyond = latest_price >= target if direction == "ABOVE" else latest_price <= target
        events.append({
            "event_type": "WATCH_LEVEL_REACHED",
            "level_id": level.id,
            "direction": direction,
            "target_price": round(target, 2),
            "event_candle_time": event_candle["timestamp"],
            "event_candle_high": round(event_candle["high"], 2),
            "event_candle_low": round(event_candle["low"], 2),
            "latest_price": round(latest_price, 2),
            "currently_beyond_level": currently_beyond,
            "max_price_after_reach": round(max(candle["high"] for candle in after_reach), 2) if direction == "ABOVE" else None,
            "min_price_after_reach": round(min(candle["low"] for candle in after_reach), 2) if direction == "BELOW" else None,
        })
    return events
