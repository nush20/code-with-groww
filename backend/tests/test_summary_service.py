import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.app.summary_service import GeminiSummaryProvider, TemplateSummaryProvider, classify_analysis


def analysis(direction="up", reversal=0, excursion=8):
    return {
        "direction": direction,
        "reversal_pct": reversal,
        "max_excursion_pct": excursion if direction == "up" else -excursion,
    }


def facts(range_name="1W", direction="up", reversal=50, session_state="COMPLETE"):
    state = classify_analysis(analysis(direction, reversal), 3.0)
    return {
        "symbol": "TEST",
        "range": range_name,
        "period_return_pct": 2.5 if direction == "up" else -2.5,
        "max_excursion_pct": 8 if direction == "up" else -8,
        "direction": direction,
        "reversal_pct": reversal,
        "semantic_state": state,
        "period_high": 108,
        "period_low": 92,
        "session_state": session_state,
    }


class SemanticClassificationTests(unittest.TestCase):
    def test_upward_reversal_boundaries(self):
        cases = [
            (29.99, "UP_MOVE_MOSTLY_HELD"),
            (30, "UP_MOVE_PARTIALLY_REVERSED"),
            (50, "UP_MOVE_PARTIALLY_REVERSED"),
            (70, "UP_MOVE_PARTIALLY_REVERSED"),
            (70.01, "UP_MOVE_MOSTLY_REVERSED"),
        ]
        for reversal, expected in cases:
            with self.subTest(reversal=reversal):
                self.assertEqual(classify_analysis(analysis("up", reversal), 3), expected)

    def test_downward_recovery_boundaries(self):
        cases = [
            (29.99, "DECLINE_MOSTLY_HELD"),
            (30, "DECLINE_PARTIALLY_RECOVERED"),
            (50, "DECLINE_PARTIALLY_RECOVERED"),
            (70, "DECLINE_PARTIALLY_RECOVERED"),
            (70.01, "DECLINE_MOSTLY_RECOVERED"),
        ]
        for recovery, expected in cases:
            with self.subTest(recovery=recovery):
                self.assertEqual(classify_analysis(analysis("down", recovery), 3), expected)

    def test_quiet_takes_precedence(self):
        self.assertEqual(classify_analysis(analysis("up", 90, 2.99), 3), "QUIET")


class TemplateSummaryTests(unittest.TestCase):
    def setUp(self):
        self.provider = TemplateSummaryProvider()

    def test_timeframe_wording(self):
        expected = {
            "1D": "latest session",
            "1W": "during the week",
            "2W": "two-week period",
            "1M": "one-month period",
        }
        for range_name, phrase in expected.items():
            with self.subTest(range_name=range_name):
                self.assertIn(phrase, self.provider.generate(facts(range_name))["summary"])

    def test_completed_session_uses_ended(self):
        self.assertIn("It ended", self.provider.generate(facts(session_state="COMPLETE"))["summary"])

    def test_in_progress_session_uses_current_language(self):
        result = self.provider.generate(facts("1D", session_state="IN_PROGRESS"))["summary"]
        self.assertIn("today", result)
        self.assertIn("is currently", result)
        self.assertNotIn("ended", result)

    def test_downward_summary_uses_recovery_not_peak(self):
        result = self.provider.generate(facts(direction="down"))
        combined = f"{result['headline']} {result['summary']}"
        self.assertIn("recover", combined.lower())
        self.assertNotIn("peak", combined.lower())

    def test_partial_recovery_does_not_claim_most_remains(self):
        summary = self.provider.generate(facts(direction="down", reversal=56))["summary"]
        self.assertIn("recovering about 56%", summary)
        self.assertNotIn("Most", summary)


class GeminiSummaryTests(unittest.TestCase):
    def test_valid_grounded_json_is_used_and_cached(self):
        models = Mock()
        models.generate_content.return_value = SimpleNamespace(text=(
            '{"headline":"TEST rose then eased","short_summary":"Rose 8%",'
            '"summary":"TEST rose 8% before 50% of the move reversed."}'
        ))
        provider = GeminiSummaryProvider()
        with patch.object(provider, "_api_key", return_value="test-key"), \
             patch("google.genai.Client", return_value=SimpleNamespace(models=models)):
            first = provider.generate(facts())
            second = provider.generate(facts())
        self.assertEqual(first, second)
        self.assertEqual(first["headline"], "TEST rose then eased")
        models.generate_content.assert_called_once()

    def test_unsupported_number_falls_back_to_template(self):
        models = Mock()
        models.generate_content.return_value = SimpleNamespace(text=(
            '{"headline":"TEST surged 99%","short_summary":"Surged 99%",'
            '"summary":"TEST surged 99%."}'
        ))
        provider = GeminiSummaryProvider()
        with patch.object(provider, "_api_key", return_value="test-key"), \
             patch("google.genai.Client", return_value=SimpleNamespace(models=models)):
            result = provider.generate(facts())
        self.assertEqual(result, TemplateSummaryProvider().generate(facts()))


if __name__ == "__main__":
    unittest.main()
