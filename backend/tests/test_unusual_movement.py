import math
import unittest
from datetime import datetime, timedelta, timezone
from statistics import stdev
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.change_detection import analyze_hidden_journey, analyze_unusual_movement
from backend.app.main import get_catchup
from backend.app.market_data import MarketDataError
from backend.app.models import UserBaseline, WatchlistItem
from backend.app.schemas import CatchupOut


START = datetime(2026, 8, 3, 4, 0, tzinfo=timezone.utc)


def daily_from_returns(returns, start=START):
    closes = [100.0]
    for value in returns:
        closes.append(closes[-1] * (1 + value / 100))
    return [{
        "timestamp": start + timedelta(days=index),
        "open": close, "high": close, "low": close, "close": close, "volume": 100,
    } for index, close in enumerate(closes)]


def catchup(prices, dates=None):
    dates = dates or [START + timedelta(minutes=5 * index) for index in range(len(prices))]
    return [{
        "timestamp": dates[index],
        "open": price, "high": price, "low": price, "close": price, "volume": 100,
    } for index, price in enumerate(prices)]


BASE_RETURNS = [1, -1] * 15
TYPICAL = stdev(BASE_RETURNS)


class UnusualMovementTests(unittest.TestCase):
    def analyze(self, excursion, history=BASE_RETURNS, journey=None, **kwargs):
        return analyze_unusual_movement(
            excursion, daily_from_returns(history), journey or catchup([100, 101]),
            minimum_history_sessions=kwargs.get("minimum", 15),
            unusual_multiple=kwargs.get("threshold", 2.0),
            volatility_epsilon=kwargs.get("epsilon", .0001),
        )

    def test_below_exactly_and_above_two_times(self):
        self.assertEqual(self.analyze(TYPICAL * 1.99)["state"], "NORMAL_RANGE")
        self.assertEqual(self.analyze(TYPICAL * 2)["state"], "UNUSUAL_MOVE")
        self.assertEqual(self.analyze(TYPICAL * 2.01)["state"], "UNUSUAL_MOVE")

    def test_positive_and_negative_excursions_use_magnitude(self):
        self.assertEqual(self.analyze(TYPICAL * 3)["significance_multiple"], 3.0)
        self.assertEqual(self.analyze(TYPICAL * -3)["significance_multiple"], 3.0)

    def test_sample_standard_deviation(self):
        result = self.analyze(2)
        self.assertAlmostEqual(result["typical_daily_movement_pct"], stdev(BASE_RETURNS), places=4)
        self.assertEqual(result["history_sessions_used"], 30)

    def test_insufficient_history(self):
        result = self.analyze(10, history=[1, -1] * 5)
        self.assertEqual(result["state"], "INSUFFICIENT_HISTORY")
        self.assertIsNone(result["significance_multiple"])

    def test_zero_and_near_zero_volatility(self):
        for returns in ([0] * 20, [0.00001, -0.00001] * 10):
            with self.subTest(returns=returns[:2]):
                result = self.analyze(5, history=returns)
                self.assertEqual(result["state"], "INSUFFICIENT_HISTORY")
                self.assertIsNone(result["significance_multiple"])

    def test_malformed_history_is_ignored(self):
        history = daily_from_returns([1, -1] * 8)
        history.extend([
            {"timestamp": START, "close": "bad"},
            {"timestamp": "bad", "close": 100},
            {"timestamp": START, "close": 0},
        ])
        result = analyze_unusual_movement(5, history, catchup([100, 101]), 15, 2, .0001)
        self.assertEqual(result["history_sessions_used"], 16)

    def test_one_session_has_floor_of_one(self):
        result = self.analyze(3, journey=catchup([100, 103]))
        self.assertEqual(result["trading_session_equivalent"], 1)
        self.assertAlmostEqual(result["expected_window_movement_pct"], TYPICAL, places=4)

    def test_multi_session_uses_square_root_scaling(self):
        dates = [START + timedelta(days=index) for index in range(4)]
        result = self.analyze(6, journey=catchup([100, 101, 102, 103], dates))
        self.assertEqual(result["trading_session_equivalent"], 4)
        self.assertAlmostEqual(result["expected_window_movement_pct"], TYPICAL * math.sqrt(4), places=4)

    def test_weekend_and_holiday_gaps_are_not_counted(self):
        friday = datetime(2026, 9, 4, 4, 0, tzinfo=timezone.utc)
        monday = datetime(2026, 9, 7, 4, 0, tzinfo=timezone.utc)
        result = self.analyze(4, journey=catchup([100, 104], [friday, monday]))
        self.assertEqual(result["trading_session_equivalent"], 2)
        holiday_gap = self.analyze(4, journey=catchup([100, 104], [friday, friday + timedelta(days=4)]))
        self.assertEqual(holiday_gap["trading_session_equivalent"], 2)

    def test_hidden_and_unusual_are_independent(self):
        baseline = START - timedelta(minutes=1)
        hidden = analyze_hidden_journey(100, baseline, catchup([100, 104, 100.5]), 100.5, 3, .4)
        self.assertTrue(hidden["is_hidden_journey"])
        self.assertEqual(self.analyze(hidden["max_excursion_pct"], history=[5, -5] * 15)["state"], "NORMAL_RANGE")

        held = analyze_hidden_journey(100, baseline, catchup([100, 103, 102.9]), 102.9, 3, .4)
        self.assertFalse(held["is_hidden_journey"])
        self.assertEqual(self.analyze(held["max_excursion_pct"], history=[.5, -.5] * 15)["state"], "UNUSUAL_MOVE")

        both = analyze_hidden_journey(100, baseline, catchup([100, 106, 100.5]), 100.5, 3, .4)
        self.assertTrue(both["is_hidden_journey"])
        self.assertEqual(self.analyze(both["max_excursion_pct"], history=[.5, -.5] * 15)["state"], "UNUSUAL_MOVE")

    def test_baseline_is_instrument_level_and_has_no_user_input(self):
        first = self.analyze(4)
        second = self.analyze(4)
        self.assertEqual(first, second)


class RowsResult:
    def __init__(self, rows): self.rows = rows
    def all(self): return self.rows


class CatchupDb:
    def __init__(self, rows, levels=None): self.rows = rows; self.levels = levels or []
    def execute(self, _query): return RowsResult(self.rows)
    def scalars(self, _query): return self.levels


class CatchupIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.context = patch("backend.app.main.company_development_service.get_developments", return_value=[])
        self.context.start()

    def tearDown(self):
        self.context.stop()

    def make_rows(self):
        baseline_time = START - timedelta(minutes=1)
        item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
        baseline = UserBaseline(
            user_id="demo-user", instrument_key="NSE_EQ|TEST", baseline_price=100,
            baseline_time=baseline_time, created_at=baseline_time, updated_at=baseline_time,
        )
        return item, baseline

    def test_unusual_and_hidden_share_one_event_and_one_dataset_fetch_each(self):
        baseline_time = START - timedelta(minutes=1)
        item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
        baseline = UserBaseline(
            user_id="demo-user", instrument_key="NSE_EQ|TEST", baseline_price=100,
            baseline_time=baseline_time, created_at=baseline_time, updated_at=baseline_time,
        )
        journey = catchup([100, 106, 100.5])
        history = daily_from_returns([.5, -.5] * 15)
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 100.5, "market_timestamp": START, "is_stale": False}) as quote, \
             patch("backend.app.main.fetch_intraday_candles", return_value=journey) as intraday, \
             patch("backend.app.main.fetch_completed_daily_candles", return_value=history) as daily:
            result = get_catchup(CatchupDb([(item, baseline)]))
        self.assertEqual(result["meaningful_count"], 1)
        self.assertTrue(result["events"][0]["is_hidden_journey"])
        self.assertEqual(result["events"][0]["unusualness"]["state"], "UNUSUAL_MOVE")
        self.assertEqual(result["events"][0]["watch_level_events"], [])
        CatchupOut.model_validate(result)
        quote.assert_called_once(); intraday.assert_called_once(); daily.assert_called_once()

    def test_provider_failure_never_creates_unusual_event(self):
        item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
        baseline = UserBaseline(
            user_id="demo-user", instrument_key="NSE_EQ|TEST", baseline_price=100,
            baseline_time=START, created_at=START, updated_at=START,
        )
        with patch("backend.app.main.fetch_latest_quote", side_effect=MarketDataError("unavailable")):
            result = get_catchup(CatchupDb([(item, baseline)]))
        self.assertEqual(result["meaningful_count"], 0)
        self.assertEqual(result["unavailable_count"], 1)

    def test_hidden_journey_alone_surfaces(self):
        item, baseline = self.make_rows()
        journey = catchup([100, 104, 100.5])
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 100.5, "market_timestamp": START, "is_stale": False}), \
             patch("backend.app.main.fetch_intraday_candles", return_value=journey), \
             patch("backend.app.main.fetch_completed_daily_candles", return_value=daily_from_returns([5, -5] * 15)):
            result = get_catchup(CatchupDb([(item, baseline)]))
        self.assertEqual(result["meaningful_count"], 1)
        self.assertTrue(result["events"][0]["is_hidden_journey"])
        self.assertEqual(result["events"][0]["unusualness"]["state"], "NORMAL_RANGE")

    def test_unusual_movement_alone_surfaces(self):
        item, baseline = self.make_rows()
        journey = catchup([100, 103, 102.9])
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 102.9, "market_timestamp": START, "is_stale": False}), \
             patch("backend.app.main.fetch_intraday_candles", return_value=journey), \
             patch("backend.app.main.fetch_completed_daily_candles", return_value=daily_from_returns([.5, -.5] * 15)):
            result = get_catchup(CatchupDb([(item, baseline)]))
        self.assertEqual(result["meaningful_count"], 1)
        self.assertFalse(result["events"][0]["is_hidden_journey"])
        self.assertEqual(result["events"][0]["unusualness"]["state"], "UNUSUAL_MOVE")

    def test_watch_level_alone_surfaces(self):
        item, baseline = self.make_rows()
        journey = catchup([100, 106, 106])
        watched_level = SimpleNamespace(id=1, instrument_key="NSE_EQ|TEST", direction="ABOVE", target_price=105, active=True)
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 106, "market_timestamp": START, "is_stale": False}), \
             patch("backend.app.main.fetch_intraday_candles", return_value=journey), \
             patch("backend.app.main.fetch_completed_daily_candles", return_value=daily_from_returns([5, -5] * 15)):
            result = get_catchup(CatchupDb([(item, baseline)], [watched_level]))
        self.assertEqual(result["meaningful_count"], 1)
        self.assertFalse(result["events"][0]["is_hidden_journey"])
        self.assertEqual(result["events"][0]["unusualness"]["state"], "NORMAL_RANGE")
        self.assertEqual(len(result["events"][0]["watch_level_events"]), 1)

    def test_all_three_signals_coexist_on_one_card(self):
        item, baseline = self.make_rows()
        journey = catchup([100, 103, 106, 110, 107, 101])
        watched_level = SimpleNamespace(id=1, instrument_key="NSE_EQ|TEST", direction="ABOVE", target_price=105, active=True)
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 101, "market_timestamp": START, "is_stale": False}) as quote, \
             patch("backend.app.main.fetch_intraday_candles", return_value=journey) as intraday, \
             patch("backend.app.main.fetch_completed_daily_candles", return_value=daily_from_returns([.5, -.5] * 15)) as daily:
            result = get_catchup(CatchupDb([(item, baseline)], [watched_level]))
        self.assertEqual(result["meaningful_count"], 1)
        event = result["events"][0]
        self.assertTrue(event["is_hidden_journey"])
        self.assertEqual(event["unusualness"]["state"], "UNUSUAL_MOVE")
        self.assertEqual(event["watch_level_events"][0]["target_price"], 105)
        quote.assert_called_once(); intraday.assert_called_once(); daily.assert_called_once()

    def test_missing_baseline_is_legitimate_empty_state_without_market_fetch(self):
        item, _ = self.make_rows()
        with patch("backend.app.main.fetch_latest_quote") as quote, \
             patch("backend.app.main.fetch_intraday_candles") as intraday, \
             patch("backend.app.main.fetch_completed_daily_candles") as daily:
            result = get_catchup(CatchupDb([(item, None)]))
        self.assertEqual(result["meaningful_count"], 0)
        self.assertEqual(result["insufficient_count"], 1)
        self.assertEqual(result["events"], [])
        quote.assert_not_called(); intraday.assert_not_called(); daily.assert_not_called()

    def test_baseline_after_newest_candle_returns_no_event(self):
        item, baseline = self.make_rows()
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": 100, "market_timestamp": baseline.baseline_time - timedelta(minutes=1), "is_stale": True}), \
             patch("backend.app.main.fetch_intraday_candles", return_value=[]), \
             patch("backend.app.main.fetch_completed_daily_candles") as daily:
            result = get_catchup(CatchupDb([(item, baseline)]))
        self.assertEqual(result["meaningful_count"], 0)
        self.assertEqual(result["insufficient_count"], 1)
        daily.assert_not_called()


if __name__ == "__main__":
    unittest.main()
