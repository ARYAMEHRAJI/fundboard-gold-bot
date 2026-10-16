import unittest
from datetime import date, timedelta

from generate_gold_technical_report import calculate_metrics, clean_closes, rsi


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
