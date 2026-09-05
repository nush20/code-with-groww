import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.change_detection import detect_watch_levels
from backend.app.database import Base
from backend.app.main import create_watch_level, delete_watch_level, mark_caught_up, remove_from_watchlist
from backend.app.models import UserBaseline, WatchLevel, WatchlistItem
from backend.app.schemas import WatchLevelCreate


START = datetime(2026, 9, 7, 4, 0, tzinfo=timezone.utc)


def candle(high, low, close=None, index=0):
    close = close if close is not None else (high + low) / 2
    return {"timestamp": START + timedelta(minutes=5 * index), "open": close, "high": high, "low": low, "close": close, "volume": 100}


def level(direction, target, identifier=1):
    return SimpleNamespace(id=identifier, direction=direction, target_price=target, active=True)


class WatchLevelDetectorTests(unittest.TestCase):
    def test_above_reached_then_returns_below(self):
        result = detect_watch_levels(100, [candle(106, 99, 104)], 103, [level("ABOVE", 105)])[0]
        self.assertFalse(result["currently_beyond_level"])
        self.assertEqual(result["max_price_after_reach"], 106)

    def test_above_reached_and_remains_above(self):
        self.assertTrue(detect_watch_levels(100, [candle(106, 100)], 106, [level("ABOVE", 105)])[0]["currently_beyond_level"])

    def test_below_reached_then_recovers_above(self):
        result = detect_watch_levels(160, [candle(161, 149.5, 152)], 153, [level("BELOW", 150)])[0]
        self.assertFalse(result["currently_beyond_level"])
        self.assertEqual(result["min_price_after_reach"], 149.5)

    def test_below_reached_and_remains_below(self):
        self.assertTrue(detect_watch_levels(160, [candle(160, 149)], 146, [level("BELOW", 150)])[0]["currently_beyond_level"])

    def test_exact_high_and_low_touches_count(self):
        self.assertEqual(len(detect_watch_levels(100, [candle(105, 101)], 104, [level("ABOVE", 105)])), 1)
        self.assertEqual(len(detect_watch_levels(160, [candle(158, 150)], 152, [level("BELOW", 150)])), 1)

    def test_ohlc_extremes_count_even_when_close_does_not(self):
        self.assertEqual(len(detect_watch_levels(100, [candle(106, 101, 103)], 103, [level("ABOVE", 105)])), 1)
        self.assertEqual(len(detect_watch_levels(160, [candle(159, 149, 153)], 153, [level("BELOW", 150)])), 1)

    def test_baseline_already_beyond_does_not_false_fire(self):
        self.assertEqual(detect_watch_levels(180, [candle(181, 176)], 180, [level("ABOVE", 175)]), [])
        self.assertEqual(detect_watch_levels(145, [candle(149, 144)], 145, [level("BELOW", 150)]), [])

    def test_level_never_reached(self):
        self.assertEqual(detect_watch_levels(100, [candle(104, 99)], 103, [level("ABOVE", 105)]), [])

    def test_multiple_touches_return_one_event(self):
        candles = [candle(106, 100, index=0), candle(107, 101, index=1)]
        self.assertEqual(len(detect_watch_levels(100, candles, 106, [level("ABOVE", 105)])), 1)

    def test_both_directions_can_fire(self):
        candles = [candle(106, 99, index=0), candle(103, 94, index=1)]
        events = detect_watch_levels(100, candles, 100, [level("ABOVE", 105, 1), level("BELOW", 95, 2)])
        self.assertEqual({event["direction"] for event in events}, {"ABOVE", "BELOW"})

    def test_recross_requires_return_to_safe_side_then_later_candle(self):
        candles = [candle(180, 170, index=0), candle(176, 171, index=1)]
        events = detect_watch_levels(178, candles, 176, [level("ABOVE", 175)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_candle_time"], candles[1]["timestamp"])

    def test_malformed_candles_do_not_fabricate_event(self):
        self.assertEqual(detect_watch_levels(100, [{"timestamp": "bad", "high": 200, "low": 1}], 100, [level("ABOVE", 105)]), [])


class WatchLevelPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
        self.db.add(self.item); self.db.commit(); self.db.refresh(self.item)

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def create(self, direction="ABOVE", target=105):
        return create_watch_level(WatchLevelCreate(instrument_key="NSE_EQ|TEST", symbol="TEST", target_price=target, direction=direction), self.db)

    def test_create_and_duplicate_direction(self):
        created = self.create()
        self.assertEqual(created.symbol, "TEST")
        with self.assertRaises(HTTPException) as caught:
            self.create(target=110)
        self.assertEqual(caught.exception.status_code, 409)

    def test_above_and_below_can_coexist(self):
        self.create("ABOVE", 105); self.create("BELOW", 95)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(WatchLevel)), 2)

    def test_invalid_target_and_direction_are_rejected(self):
        with self.assertRaises(ValidationError):
            WatchLevelCreate(instrument_key="NSE_EQ|TEST", symbol="TEST", target_price=0, direction="ABOVE")
        with self.assertRaises(ValidationError):
            WatchLevelCreate(instrument_key="NSE_EQ|TEST", symbol="TEST", target_price=100, direction="SIDEWAYS")
        with self.assertRaises(ValidationError):
            WatchLevelCreate(instrument_key="   ", symbol="TEST", target_price=100, direction="ABOVE")

    def test_delete_level_and_missing_level(self):
        created = self.create()
        response = delete_watch_level(created.id, self.db)
        self.assertEqual(response, {"message": "Watch level removed"})
        self.assertIsNone(self.db.get(WatchLevel, created.id))
        with self.assertRaises(HTTPException) as caught:
            delete_watch_level(created.id, self.db)
        self.assertEqual(caught.exception.status_code, 404)

    def test_non_watchlisted_stock_is_rejected(self):
        body = WatchLevelCreate(instrument_key="NSE_EQ|OTHER", symbol="OTHER", target_price=100, direction="ABOVE")
        with self.assertRaises(HTTPException) as caught:
            create_watch_level(body, self.db)
        self.assertEqual(caught.exception.status_code, 404)

    def test_removing_stock_cleans_levels(self):
        self.create()
        remove_from_watchlist(self.item.id, self.db)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(WatchLevel)), 0)

    def test_mark_caught_up_keeps_level_active_and_replaces_baseline(self):
        watched = self.create()
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 110}):
            mark_caught_up(self.db)
        self.assertIsNotNone(self.db.get(WatchLevel, watched.id))
        baseline = self.db.scalar(select(UserBaseline))
        self.assertEqual(baseline.baseline_price, 110)


if __name__ == "__main__":
    unittest.main()
