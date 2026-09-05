import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from backend.app.change_detection import analyze_market_session, market_session_status
from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import (
    app,
    get_market_recap,
    get_stock_detail,
    session_company_context,
    watchlist_developments_for_date,
)
from backend.app.company_developments import CompanyDevelopmentError
from backend.app.schemas import MarketRecapOut, StockDetailOut
from backend.app.market_data import MarketDataError, NSE_TIMEZONE
from backend.app.market_recap import RANGE_SESSIONS, analyze_period, select_analysis_window
from backend.app.models import WatchlistItem


START = datetime(2026, 9, 4, 3, 45, tzinfo=timezone.utc)


def session(prices, start=START):
    return [{
        "timestamp": start + timedelta(minutes=5 * index),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 100,
    } for index, price in enumerate(prices)]


class MarketRecapCalculationTests(unittest.TestCase):
    def analyze(self, prices, reference=100):
        return analyze_market_session(reference, session(prices), 3.0, 0.40)

    def test_upward_move_reverses(self):
        self.assertEqual(self.analyze([100, 106, 101])["classification"], "MOVED_THEN_REVERSED")

    def test_downward_move_reverses(self):
        result = self.analyze([100, 91, 99])
        self.assertEqual(result["classification"], "MOVED_THEN_REVERSED")
        self.assertEqual(result["direction"], "down")

    def test_upward_move_holds(self):
        self.assertEqual(self.analyze([100, 106, 105])["classification"], "MOVE_HELD")

    def test_downward_move_holds(self):
        result = self.analyze([100, 94, 94])
        self.assertEqual(result["classification"], "MOVE_HELD")
        self.assertEqual(result["direction"], "down")

    def test_move_crossing_reference_is_a_reversal(self):
        result = self.analyze([100, 106, 96])
        self.assertEqual(result["classification"], "MOVED_THEN_REVERSED")

    def test_quiet_stock(self):
        self.assertEqual(self.analyze([100, 102, 101])["classification"], "QUIET")

    def test_exact_threshold_is_meaningful(self):
        self.assertNotEqual(self.analyze([100, 103, 103])["classification"], "QUIET")

    def test_zero_reference_is_safe(self):
        self.assertEqual(self.analyze([0, 1], reference=0)["status"], "insufficient_data")

    def test_malformed_and_empty_candles(self):
        self.assertEqual(analyze_market_session(100, [], 3, .4)["status"], "insufficient_data")
        malformed = [{"timestamp": START, "open": 100, "high": "bad", "low": 99, "close": 100}]
        self.assertEqual(analyze_market_session(100, malformed, 3, .4)["status"], "insufficient_data")

    def test_after_hours_session_is_completed(self):
        after_hours = datetime(2026, 9, 5, 1, 0, tzinfo=NSE_TIMEZONE)
        self.assertEqual(market_session_status(date(2026, 9, 4), after_hours), ("completed", "Latest session"))


class FakeDb:
    def __init__(self, items): self.items = items
    def scalars(self, _query): return self.items
    def scalar(self, _query): return self.items[0] if self.items else None


class MarketRecapEndpointTests(unittest.TestCase):
    def setUp(self):
        self.context = patch("backend.app.main.session_company_context", return_value={"status": "NONE", "company_developments": []})
        self.daily_context = patch(
            "backend.app.main.watchlist_developments_for_date",
            return_value={
                "status": "NONE",
                "date": date(2026, 9, 4),
                "developments": [],
                "unavailable_count": 0,
            },
        )
        self.context.start()
        self.daily_context.start()

    def tearDown(self):
        self.context.stop()
        self.daily_context.stop()

    def test_one_unavailable_stock_does_not_break_recap(self):
        items = [
            WatchlistItem(user_id="demo-user", symbol="GOOD", company_name="Good", instrument_key="NSE_EQ|GOOD"),
            WatchlistItem(user_id="demo-user", symbol="BAD", company_name="Bad", instrument_key="NSE_EQ|BAD"),
        ]
        prior = session([99, 100], START - timedelta(days=1))
        current = session([100, 106, 101])

        def provider(key, _now, _lookback):
            if key.endswith("BAD"): raise MarketDataError("provider detail")
            return prior + current

        with patch("backend.app.main.fetch_recent_session_candles", side_effect=provider):
            response = get_market_recap(FakeDb(items), "1D")
        self.assertEqual(response["unavailable_count"], 1)
        self.assertEqual(len(response["stories"]), 1)
        self.assertEqual(response["stories"][0]["classification"], "UP_MOVE_MOSTLY_REVERSED")

    def test_invalid_range_is_a_validation_error(self):
        app.dependency_overrides[get_db] = lambda: FakeDb([])
        try:
            response = TestClient(app).get("/market-recap?range=3M")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 422)

    def test_missing_candles_returns_empty_recap(self):
        item = WatchlistItem(user_id="demo-user", symbol="EMPTY", company_name="Empty", instrument_key="NSE_EQ|EMPTY")
        with patch("backend.app.main.fetch_recent_session_candles", return_value=[]):
            response = get_market_recap(FakeDb([item]), "1D")
        self.assertEqual(response["analyzed_count"], 0)
        self.assertEqual(response["unavailable_count"], 1)

    def test_stock_detail_matches_recap_calculations(self):
        item = WatchlistItem(user_id="demo-user", symbol="MATCH", company_name="Match", instrument_key="NSE_EQ|MATCH")
        candles = trading_sessions(6)
        with patch("backend.app.main.fetch_recent_session_candles", return_value=candles):
            recap = get_market_recap(FakeDb([item]), "1W")
            detail = get_stock_detail("MATCH", FakeDb([item]), "1W")
        story = recap["stories"][0]
        self.assertEqual(detail["reference_price"], story["reference_price"])
        self.assertEqual(detail["period_return_pct"], story["session_return_pct"])
        self.assertEqual(detail["max_excursion_pct"], story["max_excursion_pct"])
        self.assertEqual(detail["semantic_state"], story["semantic_state"])
        self.assertEqual(detail["display_label"], story["display_label"])
        self.assertEqual(detail["summary"], story["summary"])
        self.assertEqual(detail["short_summary"], story["short_summary"])
        MarketRecapOut.model_validate(recap)
        StockDetailOut.model_validate(detail)

    def test_1d_recap_adds_same_day_context_and_neutral_summary_sentence(self):
        item = WatchlistItem(user_id="demo-user", symbol="NEWS", company_name="News", instrument_key="NSE_EQ|NEWS")
        candles = session([99, 100], START - timedelta(days=1)) + session([100, 106, 101])
        context = {"status": "AVAILABLE", "company_developments": [{
            "id": "news-1", "instrument_key": item.instrument_key, "symbol": item.symbol,
            "type": "EARNINGS", "headline": "Quarterly results published", "summary": None,
            "published_at": START + timedelta(hours=2), "source_name": "Upstox News",
            "source_url": "https://upstox.com/news/example", "simulated": False,
        }]}
        with patch("backend.app.main.fetch_recent_session_candles", return_value=candles), \
             patch("backend.app.main.session_company_context", return_value=context) as get_context:
            response = get_market_recap(FakeDb([item]), "1D")
        story = response["stories"][0]
        get_context.assert_called_once_with(item, date(2026, 9, 4))
        self.assertEqual(story["context"], context)
        self.assertTrue(story["summary"].endswith("A company development was also published during the session."))
        self.assertNotIn("caused", story["summary"].casefold())
        MarketRecapOut.model_validate(response)

    def test_empty_or_failed_news_does_not_break_1d_detail_summary(self):
        item = WatchlistItem(user_id="demo-user", symbol="NONE", company_name="None", instrument_key="NSE_EQ|NONE")
        candles = trading_sessions(2)
        for context in ({"status": "NONE", "company_developments": []}, {"status": "UNAVAILABLE", "company_developments": []}):
            with self.subTest(status=context["status"]), \
                 patch("backend.app.main.fetch_recent_session_candles", return_value=candles), \
                 patch("backend.app.main.session_company_context", return_value=context):
                detail = get_stock_detail("NONE", FakeDb([item]), "1D")
            self.assertEqual(detail["context"]["status"], context["status"])
            self.assertNotIn("company development was also", detail["summary"])
            StockDetailOut.model_validate(detail)

    def test_1d_stock_detail_returns_verified_context(self):
        item = WatchlistItem(user_id="demo-user", symbol="DETAIL", company_name="Detail", instrument_key="NSE_EQ|DETAIL")
        candles = trading_sessions(2)
        selected_date = candles[-1]["timestamp"].astimezone(NSE_TIMEZONE).date()
        context = {"status": "AVAILABLE", "company_developments": [{
            "id": "detail-news", "instrument_key": item.instrument_key, "symbol": item.symbol,
            "type": "DIVIDEND", "headline": "Board declared a dividend", "summary": None,
            "published_at": candles[-1]["timestamp"], "source_name": "Upstox News",
            "source_url": "https://upstox.com/news/detail", "simulated": False,
        }]}
        with patch("backend.app.main.fetch_recent_session_candles", return_value=candles), \
             patch("backend.app.main.session_company_context", return_value=context) as get_context:
            detail = get_stock_detail("DETAIL", FakeDb([item]), "1D")
        get_context.assert_called_once_with(item, selected_date)
        self.assertEqual(detail["context"]["company_developments"][0]["headline"], "Board declared a dividend")
        self.assertIn("A company development was also published during the session.", detail["summary"])

    def test_non_1d_ranges_do_not_request_company_context(self):
        item = WatchlistItem(user_id="demo-user", symbol="WEEK", company_name="Week", instrument_key="NSE_EQ|WEEK")
        with patch("backend.app.main.fetch_recent_session_candles", return_value=trading_sessions(6)), \
             patch("backend.app.main.session_company_context") as get_context:
            get_market_recap(FakeDb([item]), "1W")
            get_stock_detail("WEEK", FakeDb([item]), "1W")
        get_context.assert_not_called()


class SameDayCompanyContextTests(unittest.TestCase):
    def test_uses_full_selected_calendar_date_in_asia_kolkata(self):
        item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
        with patch("backend.app.main.company_development_service.get_developments", return_value=[]) as provider:
            result = session_company_context(item, date(2026, 9, 4))
        self.assertEqual(result["status"], "NONE")
        _, _, start, end = provider.call_args.args
        self.assertEqual(start.astimezone(NSE_TIMEZONE).isoformat(), "2026-09-04T00:00:00+05:30")
        self.assertEqual(end.astimezone(NSE_TIMEZONE).date(), date(2026, 9, 4))
        self.assertEqual((end - start) + timedelta(microseconds=1), timedelta(days=1))

    def test_provider_failure_returns_unavailable_context(self):
        item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
        with patch("backend.app.main.company_development_service.get_developments", side_effect=CompanyDevelopmentError("offline")):
            result = session_company_context(item, date(2026, 9, 4))
        self.assertEqual(result, {"status": "UNAVAILABLE", "company_developments": []})


class DailyWatchlistDevelopmentsTests(unittest.TestCase):
    def test_combines_all_watchlist_stocks_and_merges_duplicate_articles(self):
        items = [
            WatchlistItem(user_id="demo-user", symbol="TATASTEEL", company_name="Tata Steel", instrument_key="NSE_EQ|TATA"),
            WatchlistItem(user_id="demo-user", symbol="HCLTECH", company_name="HCLTech", instrument_key="NSE_EQ|HCL"),
        ]
        shared = {
            "id": "shared", "type": "OTHER_MATERIAL", "headline": "Markets close higher", "summary": None,
            "published_at": START, "source_name": "Upstox News",
            "source_url": "https://upstox.com/news/shared",
        }
        unique = {
            "id": "unique", "type": "OTHER_MATERIAL", "headline": "Tata Steel update", "summary": None,
            "published_at": START + timedelta(hours=1), "source_name": "Upstox News",
            "source_url": "https://upstox.com/news/unique",
        }

        def provider(key, *_args):
            return [shared, unique] if key.endswith("TATA") else [shared]

        with patch("backend.app.main.company_development_service.get_developments_on_date", side_effect=provider):
            result = watchlist_developments_for_date(items, date(2026, 9, 4))

        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(len(result["developments"]), 2)
        merged = next(item for item in result["developments"] if item["id"] == "shared")
        self.assertEqual(merged["symbols"], ["HCLTECH", "TATASTEEL"])

    def test_one_provider_failure_returns_partial_results(self):
        items = [
            WatchlistItem(user_id="demo-user", symbol="GOOD", company_name="Good", instrument_key="NSE_EQ|GOOD"),
            WatchlistItem(user_id="demo-user", symbol="BAD", company_name="Bad", instrument_key="NSE_EQ|BAD"),
        ]
        article = {
            "id": "news", "type": "OTHER_MATERIAL", "headline": "Company update", "summary": None,
            "published_at": START, "source_name": "Upstox News", "source_url": None,
        }

        def provider(key, *_args):
            if key.endswith("BAD"):
                raise CompanyDevelopmentError("offline")
            return [article]

        with patch("backend.app.main.company_development_service.get_developments_on_date", side_effect=provider):
            result = watchlist_developments_for_date(items, date(2026, 9, 4))

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["unavailable_count"], 1)
        self.assertEqual(result["developments"][0]["symbols"], ["GOOD"])


def trading_sessions(count, start=datetime(2026, 7, 1, 3, 45, tzinfo=timezone.utc)):
    candles = []
    day = start
    made = 0
    while made < count:
        if day.astimezone(NSE_TIMEZONE).weekday() < 5:
            price = 100 + made
            candles.extend(session([price, price + 4], day))
            made += 1
        day += timedelta(days=1)
    return candles


class MarketRecapRangeTests(unittest.TestCase):
    def test_all_supported_ranges_select_trading_sessions(self):
        candles = trading_sessions(24)
        for range_name, expected in RANGE_SESSIONS.items():
            with self.subTest(range_name=range_name):
                window = select_analysis_window(candles, range_name)
                self.assertEqual(window["session_count"], expected)
                self.assertFalse(window["is_partial"])

    def test_longer_range_uses_close_before_window(self):
        candles = trading_sessions(7)
        window = select_analysis_window(candles, "1W")
        # Session 2 is immediately before the selected five sessions and closes at 105.
        self.assertEqual(window["reference_price"], 105)

    def test_weekends_are_not_counted_as_sessions(self):
        window = select_analysis_window(trading_sessions(6), "1W")
        self.assertEqual(window["session_count"], 5)
        self.assertEqual(len({c["timestamp"].astimezone(NSE_TIMEZONE).date() for c in window["candles"]}), 5)

    def test_partial_history_is_labeled_without_fabrication(self):
        window = select_analysis_window(trading_sessions(4), "1M")
        self.assertEqual(window["session_count"], 3)
        self.assertTrue(window["is_partial"])

    def test_period_analysis_preserves_peak_and_low_times(self):
        analyzed = analyze_period(trading_sessions(6), "1W", 3.0, .4)
        _, metrics = analyzed
        self.assertIn("high_time", metrics)
        self.assertIn("low_time", metrics)


if __name__ == "__main__":
    unittest.main()
