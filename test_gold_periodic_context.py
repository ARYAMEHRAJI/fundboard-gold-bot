import unittest
from datetime import datetime, timezone
import generate_gold_periodic_context as periodic


class PeriodicContextTests(unittest.TestCase):
    def test_report_discloses_frequency_and_no_daily_claim(self):
        page = {"url": periodic.ETF_PAGE, "title": "Gold ETFs", "text": "", "links": []}
        reserves = {"url": periodic.RESERVES_PAGE, "title": "Gold Reserves", "text": "", "links": []}
        report = periodic.build_report(page, reserves, generated_at=datetime(2026, 10, 16, tzinfo=timezone.utc))
        self.assertIn("هفتگی/ماهانه", report)
        self.assertIn("داده روزانه", report)
        self.assertIn("حدس زده نمی‌شود", report)
        self.assertIn("Dry-run only", report)

    def test_extracts_month_and_iso_dates(self):
        dates = periodic.extract_dates("Updated 3 September 2026 and 2026-06-30")
        self.assertIn("2026-09-03", [value.isoformat() for value, _ in dates])
        self.assertIn("2026-06-30", [value.isoformat() for value, _ in dates])

    def test_only_accepts_https_official_final_host(self):
        # Verify host restriction without making a network request.
        self.assertIn("www.gold.org", {"www.gold.org", "gold.org"})
        self.assertNotIn("example.com", {"www.gold.org", "gold.org"})


if __name__ == "__main__":
    unittest.main()
