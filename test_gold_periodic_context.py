import unittest
from datetime import datetime, timezone
import generate_gold_periodic_context as periodic


class PeriodicContextTests(unittest.TestCase):
    def test_report_discloses_frequency_and_dry_run(self):
        page = {"url": periodic.ETF_PAGE, "title": "Gold ETFs", "text": "", "links": []}
        reserves = {"url": periodic.RESERVES_PAGE, "title": "Gold Reserves", "text": "", "links": []}
        report = periodic.build_report(page, reserves, [], [], generated_at=datetime(2026, 10, 16, tzinfo=timezone.utc))
        self.assertIn("هفتگی و ماهانه", report)
        self.assertIn("ماهانه یا فصلی", report)
        self.assertIn("Dry-run only", report)

    def test_only_accepts_official_xlsx_links(self):
        page = {"url": periodic.ETF_PAGE, "title": "ETF", "text": "", "links": [
            {"url": "https://www.gold.org/download/file/1/data.xlsx", "label": "ETF flows"},
            {"url": "https://example.com/data.xlsx", "label": "ETF flows"},
            {"url": "https://www.gold.org/article", "label": "ETF flows"},
        ]}
        found = periodic.find_xlsx_links(page, ["etf", "flow"])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["url"], "https://www.gold.org/download/file/1/data.xlsx")

    def test_access_restricted_workbook_is_explicit(self):
        result = {"url": "https://www.gold.org/download/file/1/data.xlsx", "status": "access_restricted_http_403"}
        text = "\n".join(periodic.format_workbook("ETF", result))
        self.assertIn("بدون دسترسی مجاز", text)
        self.assertIn("هیچ عددی", text)

    def test_unavailable_workbook_does_not_invent_values(self):
        result = {"url": "https://www.gold.org/data.xlsx", "status": "http_error_404"}
        text = "\n".join(periodic.format_workbook("ETF", result))
        self.assertIn("داده عددی استخراج نشد", text)


if __name__ == "__main__":
    unittest.main()
