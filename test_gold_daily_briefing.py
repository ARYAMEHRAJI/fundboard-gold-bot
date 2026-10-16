"""Offline tests for the combined daily briefing builder."""
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import build_gold_daily_briefing as builder


class DailyBriefingTests(unittest.TestCase):
    def test_combines_both_sections_and_periodic_data_caveat(self):
        generated = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
        result = builder.build_briefing("TECHNICAL SECTION", "MACRO SECTION", generated)
        self.assertIn("TECHNICAL SECTION", result)
        self.assertIn("MACRO SECTION", result)
        self.assertIn("2026-10-16T12:00:00+00:00", result)
        self.assertIn("هفتگی/ماهانه و نه داده روزانه", result)
        self.assertIn("Dry-run only", result)
        self.assertIn("gold-etfs-holdings-and-flows", result)

    def test_missing_input_is_not_silently_ignored(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "missing.txt"
            with self.assertRaises(FileNotFoundError):
                builder.read_required(path)

    def test_empty_input_is_rejected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "empty.txt"
            path.write_text("  ", encoding="utf-8")
            with self.assertRaises(ValueError):
                builder.read_required(path)


if __name__ == "__main__":
    unittest.main()
