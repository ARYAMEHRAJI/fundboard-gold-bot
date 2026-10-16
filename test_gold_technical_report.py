import unittest
from datetime import date, timedelta

from generate_gold_technical_report import (
    build_scenarios, calculate_metrics, clean_closes, find_support_resistance, rsi,
)


def sample_points(count=60, start=100.0, step=1.0):
    first_day = date(2026, 1, 1)
    return [
        {"d": (first_day + timedelta(days=i)).isoformat(), "c": str(start + i * step)}
        for i in range(count)
    ]


class GoldTechnicalMetricsTests(unittest.TestCase):
    def test_calculates_returns_and_moving_averages(self):
        metrics = calculate_metrics(sample_points(), 160.0)
        self.assertAlmostEqual(metrics["return_7_sessions_pct"], (159 / 152 - 1) * 100)
        self.assertAlmostEqual(metrics["return_30_sessions_pct"], (159 / 129 - 1) * 100)
        self.assertAlmostEqual(metrics["sma20"], sum(range(140, 160)) / 20)
        self.assertAlmostEqual(metrics["sma50"], sum(range(110, 160)) / 50)
        self.assertEqual(metrics["trend"], "bullish")


    def test_finds_close_based_support_and_resistance(self):
        closes = [
            100, 102, 105, 103, 100, 98, 101, 104, 106, 103,
            100, 97, 99, 102, 105, 108, 104, 101, 98, 95,
            98, 102, 106, 110, 107, 103, 99, 96, 100, 105,
            109, 112, 108, 104, 100, 97, 101, 106, 111, 115,
            110, 105, 100, 96, 99, 104, 109, 113, 107, 102,
            98, 95, 99, 104, 108, 112, 106, 101, 97, 94, 99,
        ]
        levels = find_support_resistance(closes)
        self.assertIsNotNone(levels["support"])
        self.assertIsNotNone(levels["resistance"])
        self.assertLess(levels["support"], closes[-1])
        self.assertGreater(levels["resistance"], closes[-1])

    def test_scenarios_have_confirmation_and_invalidation(self):
        metrics = calculate_metrics(sample_points(), 160.0)
        scenarios = build_scenarios(metrics)
        self.assertIn("bullish_confirmation", scenarios)
        self.assertIn("bullish_invalidation", scenarios)
        self.assertIn("bearish_confirmation", scenarios)
        self.assertIn("bearish_invalidation", scenarios)
        self.assertIn("روزانه", scenarios["bullish_confirmation"])

    def test_rejects_insufficient_history(self):
        with self.assertRaises(ValueError):
            calculate_metrics(sample_points(50), 150)

    def test_ignores_invalid_and_nonpositive_rows(self):
        rows = clean_closes([
            {"d": "2026-01-01", "c": "100"},
            {"d": "bad-date", "c": "101"},
            {"d": "2026-01-02", "c": "0"},
            {"d": "2026-01-01", "c": "102"},
        ])
        self.assertEqual(rows, [(date(2026, 1, 1), 102.0)])

    def test_rsi_handles_all_gains_and_flat_market(self):
        self.assertEqual(rsi(list(range(1, 16))), 100.0)
        self.assertEqual(rsi([100.0] * 15), 50.0)

    def test_rejects_nonpositive_spot(self):
        with self.assertRaises(ValueError):
            calculate_metrics(sample_points(), 0)


if __name__ == "__main__":
    unittest.main()
