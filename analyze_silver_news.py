"""Silver news intelligence: fresh Google News RSS + optional Cloudflare Workers AI. Dry-run only."""
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

TIMEOUT = 35
MAX_AGE_HOURS = 72
MAX_ARTICLES = 8
QUERY = '("silver price" OR "silver demand" OR "silver supply" OR "silver mine" OR "silver production" OR "solar silver" OR "Silver Institute") when:3d -India -Vietnam -Bundi -Kolkata -Delhi -Mumbai'
RSS_URL = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": QUERY, "hl": "en-US", "gl": "US", "ceid": "US:en"})
OUTPUT = Path("silver_content_preview/news_analysis.html")


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", s or ""))).strip()


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FundBoardSilver/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read()


def parse_news(xml_bytes, now=None):
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(xml_bytes)
    rows, seen = [], set()
    for item in root.findall(".//item"):
        title = clean(item.findtext("title", ""))
        link = clean(item.findtext("link", ""))
        summary = clean(item.findtext("description", ""))[:1200]
        source_node = item.find("source")
        source = clean(source_node.text if source_node is not None else urllib.parse.urlparse(link).netloc)
        raw_date = item.findtext("pubDate", "")
        try:
            published = parsedate_to_datetime(raw_date)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except Exception:
            continue
        age = (now - published).total_seconds() / 3600
        text = (title + " " + summary).lower()
        if not title or not link.startswith("https://") or age < -2 or age > MAX_AGE_HOURS:
            continue
        if not any(term in text for term in ("silver", "precious metal", "solar panel", "silverware")):
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append({"title": title, "link": link, "summary": summary, "source": source,
                     "published": published.isoformat(), "age_hours": round(max(0, age), 1)})
    return sorted(rows, key=lambda x: x["published"], reverse=True)[:MAX_ARTICLES]


def cloudflare_analysis(articles):
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        return None, "Cloudflare Workers AI credentials are not configured; generated no AI conclusions."
    model = os.getenv("CLOUDFLARE_AI_MODEL", "@cf/qwen/qwen3.8-27b")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    payload = {
        "messages": [
            {"role": "system", "content": "You are a cautious Persian-language precious-metals research analyst. Analyze only the supplied article titles and snippets. Separate verified facts from interpretation; explain possible bullish/bearish/neutral implications for silver, industrial demand, ETF flows, USD/rates and risk. Do not invent facts, prices, sources, or certainty. If evidence is weak, say so. This is not investment advice."},
            {"role": "user", "content": "Analyze these fresh news items in Persian. Cite item numbers inline and distinguish facts from hypotheses:\n" + json.dumps(articles, ensure_ascii=False)}
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "User-Agent": "FundBoardSilver/1.0"
    }, method="POST")
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.loads(response.read().decode("utf-8"))
    output = result.get("result", {}).get("response") or result.get("result", {}).get("output_text")
    if not output:
        raise RuntimeError("Cloudflare AI response did not contain generated text")
    return str(output).strip(), "Analysis generated with configured Cloudflare Workers AI."


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        articles = parse_news(fetch(RSS_URL))
    except Exception as exc:
        raise SystemExit(f"دریافت خبرهای تازه نقره ناموفق بود: {type(exc).__name__}")
    # Exclude local retail-price snippets that do not explain the global silver market.
    filtered = []
    for article in articles:
        combined = (article["title"] + " " + article.get("summary", "")).casefold()
        if any(term in combined for term in ("per kilogram in india", "india silver rate", "silver rate today in", "vietnam silver price", "bundi silver", "kolkata silver", "delhi silver", "mumbai silver")):
            continue
        filtered.append(article)
    if not filtered:
        raise SystemExit("خبر تازه و مرتبط با بازار جهانی نقره پیدا نشد؛ برای جلوگیری از انتشار خبر ساختگی، پست خبری ارسال نشد.")
    lines = [
        "📰 خبرهای تازه بازار جهانی نقره",
        "خبرهای زیر درباره عرضه، تقاضای صنعتی، تولید معدنی یا ابزارهای سرمایه‌گذاری نقره‌اند.",
        ""
    ]
    for article in filtered[:6]:
        # The downstream Persian editor translates and analyzes the facts; omit source names, URLs and UTC timestamps.
        published = article.get("published", "")[:10]
        lines.append(f"تاریخ انتشار: {published}")
        lines.append(f"تیتر خبر: {article['title']}")
        if article.get("summary"):
            lines.append(f"جزئیات خبر: {article['summary'][:700]}")
        lines.append("")
    report = "\n".join(lines).strip()
    OUTPUT.write_text(report, encoding="utf-8")
    print(report)
    print(f"NEWS_COUNT: {len(filtered[:6])}")
    print("TELEGRAM_MESSAGES_SENT: 0")


if __name__ == "__main__":
    main()
