import os
import unittest
from unittest.mock import patch
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

    def test_monthly_article_facts_are_attributed(self):
        page = {
            "url": "https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/09",
            "title": "Gold ETF Flows: August 2026",
            "text": "Published: 9 September, 2026 Highlights Global investors added US$18bn in August. Global holdings rose 121t. Chart 1: monthly flow Downloads:",
            "links": [],
        }
        facts = periodic.extract_public_facts(page)
        self.assertEqual(facts["published"], "9 September, 2026")
        self.assertIn("US$18bn", facts["highlights"])
        self.assertIn("121t", facts["highlights"])

    def test_latest_article_link_uses_official_monthly_path(self):
        page = {"links": [
            {"url": "https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/08", "label": "August"},
            {"url": "https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/09", "label": "September"},
            {"url": "https://example.com/gold-etfs-holdings-and-flows/2026/10", "label": "Bad"},
        ]}
        self.assertTrue(periodic.find_latest_monthly_article(page).endswith("/2026/09"))

    def test_monthly_article_probe_starts_with_current_month(self):
        page = {"links": []}
        url = periodic.find_latest_monthly_article(page, now=datetime(2026, 10, 16, tzinfo=timezone.utc))
        self.assertEqual(url, "https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/10")

    def test_optional_authorized_cookie_is_passed_only_to_official_host(self):
        class DummyResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
        with patch.dict(os.environ, {"WGC_GOLDHUB_COOKIE": "session=secret"}):
            with patch.object(periodic.urllib.request, "urlopen", return_value=DummyResponse()) as mocked:
                with periodic.request("https://www.gold.org/download/file/1/data.xlsx"):
                    pass
        req = mocked.call_args.args[0]
        self.assertEqual(req.get_header("Cookie"), "session=secret")
        with patch.dict(os.environ, {"WGC_GOLDHUB_COOKIE": "session=secret"}):
            with self.assertRaises(ValueError):
                periodic.request("https://example.com/data.xlsx")

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
