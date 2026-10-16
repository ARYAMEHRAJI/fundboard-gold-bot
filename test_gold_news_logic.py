import unittest
from datetime import datetime, timedelta, timezone

from analyze_gold_news import select_relevant_news


def article(title, source, hours_ago=1, link=None, published_override="use_default"):
    published = (
        datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        if published_override == "use_default"
        else published_override
    )
    return {
        "title": title,
        "source": source,
        "link": link or f"https://{source.lower().replace(' ', '')}.example/news/{title.lower().replace(' ', '-')}",
        "summary": "Gold market news",
        "published": published,
    }


class SelectRelevantNewsTests(unittest.TestCase):
    def test_keeps_recent_valid_articles_from_distinct_sources(self):
        items = [
            article("Gold rises after data", "Reuters", 1),
            article("Bullion steady before Fed", "Bloomberg", 2),
        ]
        selected = select_relevant_news(items)
        self.assertEqual(len(selected), 2)
        self.assertEqual({item["source"] for item in selected}, {"Reuters", "Bloomberg"})

    def test_rejects_missing_or_unparseable_publication_dates(self):
        items = [
            article("Undated gold story", "Reuters", published_override=None),
            article("Bad date gold story", "Bloomberg", published_override="not-a-date"),
        ]
        self.assertEqual(select_relevant_news(items), [])

    def test_rejects_stale_and_implausibly_future_articles(self):
        items = [
            article("Old gold story", "Reuters", 60),
            article("Future gold story", "Bloomberg",
                    published_override=datetime.now(timezone.utc) + timedelta(hours=2)),
        ]
        self.assertEqual(select_relevant_news(items), [])

    def test_rejects_non_web_links(self):
        items = [
            article("Gold story", "Reuters", link="javascript:alert(1)"),
            article("Another gold story", "Bloomberg", link="/relative/path"),
        ]
        self.assertEqual(select_relevant_news(items), [])

    def test_deduplicates_same_link_and_same_title(self):
        first = article("Gold prices edge higher", "Reuters", 1)
        same_link = article("Different title", "Bloomberg", 2, link=first["link"])
        same_title = article("Gold prices edge higher", "Other Source", 3)
        selected = select_relevant_news([first, same_link, same_title])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["title"], "Gold prices edge higher")

    def test_unknown_source_falls_back_to_link_host(self):
        item = article("Gold demand report", "Unknown source", 1,
                       link="https://example.org/gold")
        selected = select_relevant_news([item])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source"], "example.org")


if __name__ == "__main__":
    unittest.main()
