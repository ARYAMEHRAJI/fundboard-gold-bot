import unittest
from publish_gold_report import prepare_message, FOOTER


class PublishGoldReportTests(unittest.TestCase):
    def test_bold_title_and_exact_footer_links(self):
        message = prepare_message("🟡 فاندبورد طلا | گزارش\n\n📈 بخش تکنیکال\nقیمت: $2,500")
        self.assertIn("<b>🟡 فاندبورد طلا | گزارش</b>", message)
        self.assertIn('<a href="https://t.me/FundBoard_Gold">', message)
        self.assertIn("سرمایه‌گذاری شما", message)
        self.assertEqual(message.count(FOOTER), 1)

    def test_html_is_escaped(self):
        message = prepare_message("عنوان <خطرناک>\nمتن & داده")
        self.assertIn("&lt;خطرناک&gt;", message)
        self.assertIn("متن &amp; داده", message)

    def test_dry_run_and_utc_timestamp_not_published(self):
        message = prepare_message("Title\nGenerated at (UTC): 2026-10-16T00:00:00+00:00\nDry-run only: no post")
        self.assertNotIn("Generated at (UTC)", message)
        self.assertNotIn("Dry-run only", message)

    def test_long_message_keeps_footer_and_limit(self):
        message = prepare_message("Title\n" + ("متن بلند " * 800))
        self.assertLessEqual(len(message), 3900)
        self.assertTrue(message.endswith(FOOTER))


if __name__ == "__main__":
    unittest.main()
