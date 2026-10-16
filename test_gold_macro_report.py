import unittest
from datetime import date, datetime, timezone

from generate_gold_macro_report import (
    build_macro_snapshot, latest_fred_observation, parse_fed_press_releases,
)

class GoldMacroReportTests(unittest.TestCase):
    def test_latest_fred_observation_and_freshness(self):
        csv_text = "observation_date,DFII10\n2026-10-08,1.70\n2026-10-09,1.75\n"
        result = latest_fred_observation(csv_text, today=date(2026, 10, 10))
        self.assertEqual(result["date"], "2026-10-09")
        self.assertAlmostEqual(result["value"], 1.75)
        self.assertEqual(result["age_days"], 1)

    def test_rejects_stale_fred_data(self):
        with self.assertRaises(ValueError):
            latest_fred_observation(
                "observation_date,DFF\n2026-09-01,4.25\n",
                today=date(2026, 10, 1), max_age_days=10,
            )

    def test_ignores_missing_fred_values(self):
        result = latest_fred_observation(
            "observation_date,DFII10\n2026-10-08,.\n2026-10-09,1.8\n",
            today=date(2026, 10, 10),
        )
        self.assertEqual(result["value"], 1.8)

    def test_parses_recent_fed_items_and_filters_old(self):
        xml = """<rss><channel>
        <item><title>Recent policy statement</title><link>https://www.federalreserve.gov/a</link><pubDate>Fri, 09 Oct 2026 14:00:00 GMT</pubDate></item>
        <item><title>Old statement</title><link>https://www.federalreserve.gov/b</link><pubDate>Mon, 01 Jan 2024 14:00:00 GMT</pubDate></item>
        <item><title>Bad link</title><link>http://example.com</link><pubDate>Fri, 09 Oct 2026 14:00:00 GMT</pubDate></item>
        </channel></rss>"""
        items = parse_fed_press_releases(
            xml, now=datetime(2026, 10, 10, tzinfo=timezone.utc), max_age_days=14
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Recent policy statement")

    def test_macro_draft_labels_missing_data_and_source_limits(self):
        report = build_macro_snapshot({}, [], generated_at=datetime(2026, 10, 10, tzinfo=timezone.utc))
        self.assertIn("در دسترس نیست", report)
        self.assertIn("با DXY تفاوت دارد", report)
        self.assertIn("داده روزانه نیستند", report)
        self.assertIn("اطلاعیه واجد شرایطی دریافت نشد", report)

if __name__ == "__main__":
    unittest.main()
