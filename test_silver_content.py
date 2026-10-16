import unittest
from datetime import date
from generate_silver_periodic_report import pct
from analyze_silver_news import parse_news
from generate_silver_macro_report import latest
from silver_specialist_posts import TOPICS
from silver_content_suite import rsi, YAHOO

class SilverContentTests(unittest.TestCase):
    def test_pct_return(self):
        self.assertAlmostEqual(pct(110, 100), 10.0)
        self.assertAlmostEqual(pct(90, 100), -10.0)
    def test_rsi_bounded_for_mixed_prices(self):
        value = rsi([10, 11, 10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18], 14)
        self.assertGreaterEqual(value, 0)
        self.assertLessEqual(value, 100)
    def test_specialist_library_is_not_empty(self):
        self.assertGreaterEqual(len(TOPICS), 8)
        for topic in TOPICS:
            self.assertGreaterEqual(len(topic), 4)
    def test_news_parser_rejects_invalid_xml(self):
        with self.assertRaises(Exception):
            parse_news(b"not xml")
    def test_macro_stale_data_rejected(self):
        with self.assertRaises(ValueError):
            latest("observation_date,DFII10\n2000-01-01,1.0\n", today=date(2026, 1, 1))
    def test_yahoo_symbol_map_has_silver_and_gold(self):
        self.assertIn("silver", YAHOO)
        self.assertIn("gold", YAHOO)

if __name__ == "__main__":
    unittest.main()
