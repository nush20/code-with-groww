import unittest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app import main
from backend.app.change_detection import analyze_hidden_journey, analyze_unusual_movement, detect_watch_levels
from backend.app.database import Base
from backend.app.demo_market_data import replay_examples, replay_inputs
from backend.app.market_data import MarketDataError
from backend.app.models import UserBaseline, WatchLevel, WatchlistItem
from backend.app.schemas import CatchupOut


class DemoReplayTests(unittest.TestCase):
    def test_fixture_contains_only_inputs_and_real_source_traceability(self):
        fixture_path = Path(__file__).parents[1] / "app" / "fixtures" / "pinelabs_historical_replay.json"
        raw = json.loads(fixture_path.read_text())
        self.assertEqual(len(raw["journey_candles"]), 49)
        self.assertEqual(len(raw["historical_daily_candles"]), 31)
        self.assertNotIn("excursion_pct", raw)
        self.assertNotIn("reversal_pct", raw)
        self.assertNotIn("unusualness", raw)
        self.assertEqual(raw["development"]["source_name"], "Upstox News")
        self.assertTrue(raw["development"]["source_url"].startswith("https://upstox.com/news/"))
        published = datetime.fromisoformat(raw["development"]["published_at"])
        self.assertGreaterEqual(published, datetime.fromisoformat(raw["baseline_time"]))
        self.assertLessEqual(published, datetime.fromisoformat(raw["journey_candles"][-1]["timestamp"]))

    def test_historical_replay_calculates_hidden_journey_and_watch_level(self):
        result = main.get_catchup_demo()
        self.assertEqual(result["mode"], "demo")
        self.assertEqual(result["meaningful_count"], 3)
        event = result["events"][0]
        self.assertEqual(event["symbol"], "PINELABS")
        self.assertTrue(event["is_hidden_journey"])
        self.assertEqual(len(event["watch_level_events"]), 1)
        self.assertEqual(event["watch_level_events"][0]["target_price"], 164)
        self.assertFalse(event["watch_level_events"][0]["currently_beyond_level"])
        self.assertEqual(event["unusualness"]["state"], "NORMAL_RANGE")
        self.assertEqual(event["excursion"]["return_pct"], 3.8)
        self.assertEqual(event["reversal_pct"], 63.97)
        self.assertEqual(event["unusualness"]["typical_daily_movement_pct"], 3.0806)
        self.assertEqual(event["unusualness"]["significance_multiple"], 0.87)
        self.assertEqual(event["context"]["status"], "AVAILABLE")
        self.assertEqual(event["context"]["company_developments"][0]["source_name"], "Upstox News")
        self.assertFalse(event["context"]["company_developments"][0]["simulated"])
        CatchupOut.model_validate(result)

    def test_values_match_direct_production_detector_calculations(self):
        replay = replay_inputs()
        hidden = analyze_hidden_journey(
            replay["baseline_price"], replay["baseline_time"], replay["candles"],
            replay["latest"]["price"], 3.0, 0.40,
        )
        levels = detect_watch_levels(
            replay["baseline_price"], replay["candles"], replay["latest"]["price"], replay["levels"],
        )
        unusual = analyze_unusual_movement(hidden["max_excursion_pct"], replay["daily_candles"], replay["candles"])
        event = main.get_catchup_demo()["events"][0]
        self.assertEqual(event["excursion"]["return_pct"], hidden["max_excursion_pct"])
        self.assertEqual(event["reversal_pct"], hidden["reversal_pct"])
        self.assertEqual(event["watch_level_events"], levels)
        self.assertEqual(event["unusualness"], unusual)

    def test_demo_calls_shared_production_pipeline_and_detectors(self):
        with patch("backend.app.main.build_catchup_event", wraps=main.build_catchup_event) as pipeline, \
             patch("backend.app.main.analyze_hidden_journey", wraps=analyze_hidden_journey) as hidden, \
             patch("backend.app.main.detect_watch_levels", wraps=detect_watch_levels) as levels, \
             patch("backend.app.main.analyze_unusual_movement", wraps=analyze_unusual_movement) as unusual:
            main.get_catchup_demo()
        self.assertEqual(pipeline.call_count, 3)
        self.assertEqual(hidden.call_count, 3); self.assertEqual(levels.call_count, 3); self.assertEqual(unusual.call_count, 3)

    def test_combined_gallery_uses_three_real_inputs_and_combined_signals(self):
        result = main.get_catchup_demo()
        self.assertEqual({event["symbol"] for event in result["events"]}, {"PINELABS", "INFOBEAN", "TATATECH"})
        self.assertTrue(all(event["is_hidden_journey"] for event in result["events"][:3]))
        self.assertEqual(len(replay_examples()), 3)
        events = {event["symbol"]: event for event in result["events"]}
        self.assertEqual(events["INFOBEAN"]["watch_level_events"], [])
        self.assertEqual(events["INFOBEAN"]["unusualness"]["state"], "UNUSUAL_MOVE")
        self.assertTrue(events["PINELABS"]["watch_level_events"])
        self.assertTrue(events["TATATECH"]["watch_level_events"])
        self.assertEqual(events["INFOBEAN"]["context"]["status"], "NONE")
        self.assertEqual(events["TATATECH"]["context"]["status"], "NONE")

    def test_repeated_demo_is_deterministic(self):
        self.assertEqual(main.get_catchup_demo(), main.get_catchup_demo())

    def test_three_scenarios_use_the_same_real_fixture_with_different_user_state(self):
        combined = main.get_catchup_demo("combined")["events"][0]
        hidden = main.get_catchup_demo("hidden-reversal")["events"][0]
        personal = main.get_catchup_demo("personal-level")["events"][0]

        self.assertTrue(combined["is_hidden_journey"])
        self.assertTrue(combined["watch_level_events"])
        self.assertTrue(hidden["is_hidden_journey"])
        self.assertEqual(hidden["watch_level_events"], [])
        self.assertFalse(personal["is_hidden_journey"])
        self.assertEqual(personal["watch_level_events"][0]["target_price"], 162)
        self.assertEqual(personal["context"]["status"], "NONE")

    def test_demo_does_not_mutate_real_database_state(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        item = WatchlistItem(user_id="demo-user", symbol="REAL", company_name="Real", instrument_key="NSE_EQ|REAL")
        baseline = UserBaseline(user_id="demo-user", instrument_key="NSE_EQ|REAL", baseline_price=200, baseline_time=now, created_at=now, updated_at=now)
        level = WatchLevel(user_id="demo-user", instrument_key="NSE_EQ|REAL", symbol="REAL", target_price=210, direction="ABOVE", active=True, created_at=now, updated_at=now)
        db.add_all([item, baseline, level]); db.commit()
        before = tuple(db.scalar(select(func.count()).select_from(model)) for model in (WatchlistItem, UserBaseline, WatchLevel))
        main.get_catchup_demo(); main.get_catchup_demo()
        after = tuple(db.scalar(select(func.count()).select_from(model)) for model in (WatchlistItem, UserBaseline, WatchLevel))
        self.assertEqual(before, after)
        self.assertEqual(db.scalar(select(WatchlistItem)).symbol, "REAL")
        self.assertEqual(db.scalar(select(UserBaseline)).baseline_price, 200)
        self.assertEqual(db.scalar(select(WatchLevel)).target_price, 210)
        db.close(); engine.dispose()

    def test_live_provider_failure_never_falls_back_to_demo(self):
        item = WatchlistItem(user_id="demo-user", symbol="REAL", company_name="Real", instrument_key="NSE_EQ|REAL")
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        baseline = UserBaseline(user_id="demo-user", instrument_key="NSE_EQ|REAL", baseline_price=100, baseline_time=now, created_at=now, updated_at=now)

        class Rows:
            def all(self): return [(item, baseline)]
        class Db:
            def execute(self, _query): return Rows()
            def scalars(self, _query): return []

        with patch("backend.app.main.fetch_latest_quote", side_effect=MarketDataError("offline")) as upstox, \
             patch("backend.app.main.replay_inputs") as replay:
            result = main.get_catchup(Db())
        upstox.assert_called_once(); replay.assert_not_called()
        self.assertEqual(result["events"], [])
        self.assertEqual(result["unavailable_count"], 1)


if __name__ == "__main__":
    unittest.main()
