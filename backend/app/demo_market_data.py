"""Immutable historical inputs for the explicit Catch-Up replay experience."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "pinelabs_historical_replay.json"
EXAMPLE_FIXTURE_PATHS = (
    FIXTURE_PATH,
    Path(__file__).with_name("fixtures") / "infobean_historical_replay.json",
    Path(__file__).with_name("fixtures") / "tatatech_historical_replay.json",
)
REPLAY_SCENARIOS = {
    "combined": {
        "name": "Complete Catch-Up example", "description": "A personal watch level and a hidden round trip happened in the same absence window.",
        "start_index": 0, "watch_level": None, "include_development": True,
    },
    "hidden-reversal": {
        "name": "Round trip", "description": "A meaningful intraday rise became much less visible in the latest price.",
        "start_index": 0, "watch_level": False, "include_development": True,
    },
    "personal-level": {
        "name": "Watch level only", "description": "A personal below-price level was reached without a hidden-journey alert.",
        "start_index": 20, "watch_level": {"id": -162, "direction": "BELOW", "target_price": 162.0, "active": True},
        "include_development": False,
    },
}


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _candle(raw: dict) -> dict:
    return {**raw, "timestamp": _timestamp(raw["timestamp"])}


def _combined_replay(raw: dict, scenario: dict) -> dict:
    candles = [_candle(candle) for candle in raw["journey_candles"]]
    development = raw.get("development")
    developments = []
    if development:
        developments.append({**development, "published_at": _timestamp(development["published_at"])})
    return {
        "item": SimpleNamespace(
            instrument_key=raw["instrument_key"],
            symbol=raw["symbol"],
            company_name=raw["company_name"],
        ),
        "baseline_price": raw["baseline_price"],
        "baseline_time": _timestamp(raw["baseline_time"]),
        "latest": {
            "price": candles[-1]["close"],
            "market_timestamp": candles[-1]["timestamp"],
            "is_stale": False,
        },
        "candles": candles,
        "daily_candles": [_candle(candle) for candle in raw["historical_daily_candles"]],
        "levels": [SimpleNamespace(**raw["watch_level"], instrument_key=raw["instrument_key"])],
        "developments": developments,
        "scenario": scenario,
    }


def replay_examples() -> list[dict]:
    """Load every real-market combined-signal example for the demo gallery."""
    examples = []
    for path in EXAMPLE_FIXTURE_PATHS:
        raw = json.loads(path.read_text())
        examples.append(_combined_replay(raw, {
            "id": raw["symbol"].casefold(),
            "name": f"{raw['company_name']} Catch-Up",
            "description": "A replayed personal watch level and a hidden journey occurred in the same historical session.",
        }))
    return examples


def replay_inputs(scenario: str = "combined") -> dict:
    """Load snapshotted Upstox inputs; calculated conclusions are not stored here."""
    if scenario not in REPLAY_SCENARIOS:
        raise ValueError(f"Unknown replay scenario: {scenario}")
    raw = json.loads(FIXTURE_PATH.read_text())
    all_candles = [_candle(candle) for candle in raw["journey_candles"]]
    config = REPLAY_SCENARIOS[scenario]
    start_index = config["start_index"]
    candles = all_candles[start_index:]
    development = {**raw["development"], "published_at": _timestamp(raw["development"]["published_at"])}
    level = raw["watch_level"] if config["watch_level"] is None else config["watch_level"]
    baseline_price = raw["baseline_price"] if start_index == 0 else all_candles[start_index - 1]["close"]
    baseline_time = _timestamp(raw["baseline_time"]) if start_index == 0 else all_candles[start_index - 1]["timestamp"]
    return {
        "item": SimpleNamespace(
            instrument_key=raw["instrument_key"],
            symbol=raw["symbol"],
            company_name=raw["company_name"],
        ),
        "baseline_price": baseline_price,
        "baseline_time": baseline_time,
        "latest": {
            "price": candles[-1]["close"],
            "market_timestamp": candles[-1]["timestamp"],
            "is_stale": False,
        },
        "candles": candles,
        "daily_candles": [_candle(candle) for candle in raw["historical_daily_candles"]],
        "levels": [] if level is False else [SimpleNamespace(**level, instrument_key=raw["instrument_key"])],
        "developments": [development] if config["include_development"] else [],
        "scenario": {"id": scenario, "name": config["name"], "description": config["description"]},
    }
