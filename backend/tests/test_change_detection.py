import unittest
from datetime import datetime, timedelta, timezone

from backend.app.change_detection import analyze_hidden_journey


START = datetime(2026, 9, 5, 4, 30, tzinfo=timezone.utc)


def candles(prices):
    return [{
        "timestamp": START + timedelta(minutes=index + 1),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 100,
    } for index, price in enumerate(prices)]


class HiddenJourneyTests(unittest.TestCase):
    def analyze(self, path, current=None, baseline=100):
        return analyze_hidden_journey(
            baseline, START, candles(path), current if current is not None else path[-1], 3.0, 0.40
        )

    def test_hidden_upward_journey(self):
        result = self.analyze([100, 104, 106, 101])
        self.assertTrue(result["is_hidden_journey"])
        self.assertEqual(result["excursion_direction"], "up")
        self.assertEqual(result["max_excursion_pct"], 6.0)
        self.assertEqual(result["current_return_pct"], 1.0)

    def test_hidden_downward_journey(self):
        result = self.analyze([100, 96, 91, 99])
        self.assertTrue(result["is_hidden_journey"])
        self.assertEqual(result["excursion_direction"], "down")
        self.assertEqual(result["max_excursion_pct"], -9.0)
        self.assertEqual(result["current_return_pct"], -1.0)

    def test_move_remains_visible(self):
        self.assertFalse(self.analyze([100, 102, 105, 105])["is_hidden_journey"])

    def test_tiny_movement(self):
        self.assertFalse(self.analyze([100, 101, 100.5])["is_hidden_journey"])

    def test_no_data_is_insufficient(self):
        result = analyze_hidden_journey(100, START, [], 100, 3.0, 0.40)
        self.assertEqual(result["status"], "insufficient_data")

    def test_zero_baseline_does_not_crash(self):
        result = analyze_hidden_journey(0, START, candles([0, 1]), 1, 3.0, 0.40)
        self.assertEqual(result["status"], "insufficient_data")

    def test_zero_excursion_denominator_does_not_crash(self):
        result = self.analyze([100, 100], current=100)
        self.assertEqual(result["reversal_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
