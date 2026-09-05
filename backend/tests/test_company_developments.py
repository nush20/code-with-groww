from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.app import main
from backend.app.company_developments import (
    CompanyDevelopmentError,
    CompanyDevelopmentService,
    UpstoxCompanyDevelopmentProvider,
    normalize_upstox_development,
)
from backend.app.demo_market_data import replay_inputs
from backend.app.models import UserBaseline, WatchlistItem
from backend.app.schemas import CatchupOut, CompanyDevelopmentOut
from backend.app.summary_service import TemplateSummaryProvider


NOW = datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc)


def development(headline="Quarterly results announced", when=NOW, identifier="one"):
    return {
        "id": identifier,
        "instrument_key": "NSE_EQ|TEST",
        "symbol": "TEST",
        "type": "EARNINGS",
        "headline": headline,
        "summary": "Verified filing summary",
        "published_at": when,
        "source_name": "Upstox News",
        "source_url": "https://upstox.com/news/example",
        "simulated": False,
    }


class Provider:
    def __init__(self, items): self.items = items; self.calls = 0
    def get_recent_developments(self, instrument_key, symbol): self.calls += 1; return self.items


class DevelopmentProviderTests(unittest.TestCase):
    def test_earnings_normalizes_without_provider_fields(self):
        raw = {"heading": "Quarterly results announced", "summary": "Revenue increased", "article_link": "https://upstox.com/news/a", "published_time": int(NOW.timestamp() * 1000), "thumbnail": "private", "vendor_rank": 4}
        result = normalize_upstox_development("NSE_EQ|TEST", "TEST", raw)
        self.assertEqual(result["type"], "EARNINGS")
        self.assertEqual(result["published_at"], NOW)
        self.assertEqual(result["source_name"], "Upstox News")
        self.assertNotIn("thumbnail", result); self.assertNotIn("vendor_rank", result)
        CompanyDevelopmentOut.model_validate(result)

    def test_provider_summary_is_cleaned_and_shortened_without_generated_copy(self):
        raw = {
            "heading": "Company update", "article_link": "https://upstox.com/news/a",
            "published_time": int(NOW.timestamp() * 1000),
            "summary": "<p>First factual sentence.</p> Second factual sentence. Third sentence is not included.",
        }
        result = normalize_upstox_development("NSE_EQ|TEST", "TEST", raw)
        self.assertEqual(result["summary"], "First factual sentence. Second factual sentence.")

    def test_corporate_actions_normalize(self):
        for headline, expected in (("Board declares final dividend", "DIVIDEND"), ("Company announces stock split", "STOCK_SPLIT"), ("Board approves share buyback", "BUYBACK")):
            with self.subTest(headline=headline):
                raw = {"heading": headline, "article_link": "https://upstox.com/news/a", "published_time": int(NOW.timestamp() * 1000)}
                self.assertEqual(normalize_upstox_development("NSE_EQ|TEST", "TEST", raw)["type"], expected)

    def test_upstox_adapter_uses_instrument_news_and_normalizes(self):
        raw = {"heading": "Company wins order", "summary": "A contract was signed", "article_link": "https://upstox.com/news/a", "published_time": int(NOW.timestamp() * 1000)}
        with patch("backend.app.company_developments._upstox_get", return_value={"data": {"NSE_EQ|TEST": [raw]}}) as fetch:
            result = UpstoxCompanyDevelopmentProvider().get_recent_developments("NSE_EQ|TEST", "TEST")
        self.assertEqual(result[0]["type"], "MAJOR_ORDER_OR_DEAL")
        self.assertEqual(fetch.call_args.kwargs["params"]["category"], "instrument_keys")

    def test_window_filter_deduplication_low_value_filter_and_cap(self):
        items = [
            development(when=NOW - timedelta(hours=2), identifier="before"),
            development(when=NOW + timedelta(hours=2), identifier="after"),
            development("Quarterly results announced", NOW, "duplicate-a"),
            development("Quarterly   results announced!", NOW + timedelta(minutes=1), "duplicate-b"),
            development("Stocks to watch: TEST", NOW, "low-value"),
            development("CEO appointment announced", NOW, "management"),
            development("Major contract signed", NOW, "deal"),
            development("Dividend declared", NOW, "dividend"),
        ]
        service = CompanyDevelopmentService(Provider(items))
        with patch.dict("os.environ", {"COMPANY_DEVELOPMENT_LIMIT": "3"}):
            result = service.get_developments("NSE_EQ|TEST", "TEST", NOW - timedelta(hours=1), NOW + timedelta(hours=1))
        self.assertEqual(len(result), 3)
        self.assertNotIn("before", {item["id"] for item in result})
        self.assertNotIn("after", {item["id"] for item in result})
        self.assertNotIn("low-value", {item["id"] for item in result})
        self.assertEqual(sum("Quarterly" in item["headline"] for item in result), 1)

    def test_shared_instrument_cache_is_reused_across_user_windows(self):
        provider = Provider([development()])
        service = CompanyDevelopmentService(provider)
        service.get_developments("NSE_EQ|TEST", "TEST", NOW - timedelta(hours=1), NOW + timedelta(hours=1))
        service.get_developments("NSE_EQ|TEST", "TEST", NOW - timedelta(days=1), NOW + timedelta(days=1))
        self.assertEqual(provider.calls, 1)

    def test_daily_watchlist_feed_uses_india_date_and_keeps_generic_mapped_news(self):
        india = ZoneInfo("Asia/Kolkata")
        items = [
            development("Top gainers and losers: TEST advances", datetime(2026, 9, 3, 19, 0, tzinfo=timezone.utc), "same-day"),
            development("Previous session update", datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc), "previous-day"),
        ]
        service = CompanyDevelopmentService(Provider(items))

        result = service.get_developments_on_date("NSE_EQ|TEST", "TEST", date(2026, 9, 4), india)

        self.assertEqual([item["id"] for item in result], ["same-day"])


class Rows:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class Db:
    def __init__(self, rows): self.rows = rows
    def execute(self, _query): return Rows(self.rows)
    def scalars(self, _query): return []


def market_rows():
    baseline_time = NOW - timedelta(minutes=31)
    item = WatchlistItem(user_id="demo-user", symbol="TEST", company_name="Test", instrument_key="NSE_EQ|TEST")
    baseline = UserBaseline(user_id="demo-user", instrument_key="NSE_EQ|TEST", baseline_price=100, baseline_time=baseline_time, created_at=baseline_time, updated_at=baseline_time)
    return item, baseline


def candles(prices):
    return [{"timestamp": NOW - timedelta(minutes=25 - index * 5), "open": price, "high": price, "low": price, "close": price, "volume": 100} for index, price in enumerate(prices)]


def history():
    closes = [100]
    for value in [.5, -.5] * 15: closes.append(closes[-1] * (1 + value / 100))
    return [{"timestamp": NOW - timedelta(days=40-index), "open": close, "high": close, "low": close, "close": close, "volume": 100} for index, close in enumerate(closes)]


class CatchupContextTests(unittest.TestCase):
    def run_catchup(self, journey):
        item, baseline = market_rows()
        with patch("backend.app.main.fetch_latest_quote", return_value={"price": journey[-1]["close"], "market_timestamp": journey[-1]["timestamp"], "is_stale": False}), \
             patch("backend.app.main.fetch_intraday_candles", return_value=journey), \
             patch("backend.app.main.fetch_completed_daily_candles", return_value=history()):
            return main.get_catchup(Db([(item, baseline)]))

    def test_meaningful_event_retrieves_context_but_quiet_stock_does_not(self):
        with patch("backend.app.main.company_development_service.get_developments", return_value=[development()]) as get_context:
            meaningful = self.run_catchup(candles([100, 106, 100.5]))
        get_context.assert_called_once()
        self.assertEqual(meaningful["events"][0]["context"]["status"], "AVAILABLE")

        with patch("backend.app.main.company_development_service.get_developments") as get_context:
            quiet = self.run_catchup(candles([100, 101, 100.5]))
        get_context.assert_not_called(); self.assertEqual(quiet["events"], [])

    def test_provider_failure_keeps_market_event(self):
        with patch("backend.app.main.company_development_service.get_developments", side_effect=CompanyDevelopmentError("offline")):
            result = self.run_catchup(candles([100, 106, 100.5]))
        self.assertEqual(result["meaningful_count"], 1)
        self.assertEqual(result["events"][0]["context"]["status"], "UNAVAILABLE")

    def test_no_context_is_honest_and_schema_is_normalized(self):
        with patch("backend.app.main.company_development_service.get_developments", return_value=[]):
            result = self.run_catchup(candles([100, 106, 100.5]))
        event = result["events"][0]
        self.assertEqual(event["context"], {"status": "NONE", "company_developments": []})
        self.assertNotIn("caused", event["summary"].casefold())
        CatchupOut.model_validate(result)

    def test_historical_replay_context_is_real_and_ephemeral(self):
        result = main.get_catchup_demo()
        context = result["events"][0]["context"]
        self.assertEqual(context["status"], "AVAILABLE")
        self.assertFalse(context["company_developments"][0]["simulated"])
        self.assertIn("upstox.com/news/", context["company_developments"][0]["source_url"])
        self.assertEqual(replay_inputs()["developments"], replay_inputs()["developments"])


class CatchupSummaryTests(unittest.TestCase):
    def facts(self, hidden=True, level=True, unusual=True, context=True):
        return {
            "summary_kind": "catchup", "symbol": "TEST", "headline": "Facts",
            "market_facts": {"direction": "up", "max_excursion_pct": 7.8, "reversal_pct": 84,
                             "latest_return_pct": 1.2, "is_hidden_journey": hidden,
                             "significance_multiple": 2.7 if unusual else None},
            "personal_facts": {"watch_levels_reached": [175] if level else []},
            "company_developments": [development()] if context else [],
        }

    def test_summary_handles_each_signal_and_all_signals(self):
        provider = TemplateSummaryProvider()
        for options in (
            dict(hidden=True, level=False, unusual=False),
            dict(hidden=False, level=True, unusual=False),
            dict(hidden=False, level=False, unusual=True),
            dict(hidden=True, level=True, unusual=True),
        ):
            with self.subTest(options=options):
                summary = provider.generate(self.facts(**options))["summary"]
                self.assertIn("7.80%", summary)
                self.assertNotIn("caused", summary.casefold())

    def test_summary_keeps_context_out_of_the_price_explanation(self):
        summary = TemplateSummaryProvider().generate(self.facts())["summary"]
        self.assertNotIn("Quarterly results announced", summary)
        for forbidden in ("caused", "drove", "reacted positively", "because"):
            self.assertNotIn(forbidden, summary.casefold())

    def test_summary_without_development_invents_nothing(self):
        summary = TemplateSummaryProvider().generate(self.facts(context=False))["summary"]
        self.assertNotIn("development", summary.casefold())
        self.assertNotIn("results", summary.casefold())


if __name__ == "__main__":
    unittest.main()
