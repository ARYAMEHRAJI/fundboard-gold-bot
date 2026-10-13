
import os
import re
import html
import json
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlparse


# -----------------------------
# Configuration
# -----------------------------

NEWS_URL = "https://news.google.com/rss/search?"
NEWS_QUERY = (
    '"spot gold" OR "gold futures" OR "gold bullion" OR '
    '"XAU/USD" OR ("gold price" AND '
    '(Fed OR inflation OR dollar OR "Treasury yields" '
    'OR "central bank" OR geopolitics)) when:1d'
)

MODEL = "@cf/qwen/qwen3.8-27b"

MAX_ARTICLES = 20
MAX_AGE_HOURS = 18
MAX_ARTICLES_FOR_ANALYSIS = 8
MAX_TOKENS = 1600


# -----------------------------
# Text cleaning
# -----------------------------

def clean_text(value):
    """Remove HTML tags and normalize text."""
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def is_relevant_article(article):
    """Keep articles relevant to gold or gold-related market drivers."""
    title = clean_text(article.get("title", "")).lower()
    description = clean_text(article.get("description", "")).lower()

    gold_terms = (
        "gold",
        "bullion",
        "xau",
        "precious metal",
    )

    macro_terms = (
        "federal reserve",
        "fed ",
        "interest rate",
        "inflation",
        "us dollar",
        "dollar",
        "treasury yield",
        "bond yield",
        "central bank",
        "geopolitical",
        "geopolitics",
        "safe haven",
    )

    if any(term in title for term in gold_terms):
        return True

    has_macro = any(
        term in title or term in description
        for term in macro_terms
    )
    has_gold_context = any(
        term in title or term in description
        for term in gold_terms
    )

    return has_macro and has_gold_context


# -----------------------------
# News collection
# -----------------------------

def fetch_news():
    """Fetch recent gold-market news from Google News RSS."""
    params = urllib.parse.urlencode({
        "q": NEWS_QUERY,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })

    url = NEWS_URL + params

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 FundBoardGoldBot/1.0"
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

    except Exception as exc:
        raise RuntimeError(
            f"Could not fetch Google News RSS: {exc}"
        ) from exc

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)

    articles = []
    seen_links = set()

    for item in root.findall(".//item"):
        title = clean_text(
            item.findtext("title", default="")
        )
        link = clean_text(
            item.findtext("link", default="")
        )
        description = clean_text(
            item.findtext("description", default="")
        )
        pub_date = clean_text(
            item.findtext("pubDate", default="")
        )

        source_element = item.find("source")
        source = (
            clean_text(source_element.text or "")
            if source_element is not None
            else ""
        )

        if not title or not link or link in seen_links:
            continue

        published_at = None

        if pub_date:
            try:
                published_at = parsedate_to_datetime(pub_date)

                if published_at.tzinfo is None:
                    published_at = published_at.replace(
                        tzinfo=timezone.utc
                    )
                else:
                    published_at = published_at.astimezone(
                        timezone.utc
                    )

            except (TypeError, ValueError, OverflowError):
                published_at = None

        # Skip articles whose publication time is known
        # to be outside the selected time window.
        if published_at and published_at < cutoff:
            continue

        article = {
            "title": title,
            "link": link,
            "description": description,
            "source": source or (
                urlparse(link).hostname or "Unknown source"
            ),
            "published": (
                published_at.isoformat()
                if published_at
                else pub_date
            ),
        }

        if not is_relevant_article(article):
            continue

        articles.append(article)
        seen_links.add(link)

        if len(articles) >= MAX_ARTICLES:
            break

    return articles


# -----------------------------
# Article selection
# -----------------------------

def select_relevant_news(articles, limit=MAX_ARTICLES_FOR_ANALYSIS):
    """Prioritize gold-specific headlines and diversify sources."""
    gold_terms = ("gold", "bullion", "xau", "precious metal")

    ranked = sorted(
        articles,
        key=lambda article: (
            not any(
                term in article.get("title", "").lower()
                for term in gold_terms
            ),
            article.get("published", ""),
        ),
        reverse=False,
    )

    selected = []
    seen_titles = set()

    for article in ranked:
        normalized_title = article.get("title", "").lower()

        if normalized_title in seen_titles:
            continue

        selected.append(article)
        seen_titles.add(normalized_title)

        if len(selected) >= limit:
            break

    return selected


# -----------------------------
# Analysis prompt
# -----------------------------

def build_prompt(articles):
    """Build a grounded analysis prompt using real article data."""
    news_text = []

    for index, article in enumerate(articles, start=1):
        news_text.append(
            f"{index}. عنوان: {article.get('title', '')}\n"
            f"منبع: {article.get('source', '')}\n"
            f"زمان انتشار: {article.get('published', 'نامشخص')}\n"
            f"خلاصه خبر: {article.get('description', '')[:900]}"
        )

    joined_news = "\n\n".join(news_text)

    return f"""
تو تحلیلگر بازار جهانی طلا برای رسانه فاندبورد هستی.

بر اساس خبرهای واقعی زیر، یک تحلیل فارسی روان، دقیق و مستقل
برای انتشار در کانال تلگرامی تهیه کن.

قواعد مهم:
- فقط از اطلاعات موجود در خبرها استفاده کن.
- قیمت لحظه‌ای طلا، درصد تغییر، آمار یا نقل‌قولی را که
  در داده‌ها وجود ندارد، اختراع نکن.
- خبر، برداشت تحلیلی و سناریوی احتمالی را از یکدیگر جدا کن.
- اثر احتمالی نرخ بهره آمریکا، دلار، بازده اوراق خزانه،
  تورم و ریسک‌های ژئوپلیتیک را فقط در صورت ارتباط با خبرها
  توضیح بده.
- اگر شواهد کافی برای نتیجه‌گیری وجود ندارد، صریحاً بگو.
- از پیش‌بینی قطعی قیمت و توصیه خرید یا فروش خودداری کن.
- خبرهای تکراری را ادغام کن.
- متن مختصر، کاربردی و مناسب تلگرام باشد.
- از تیتر جذاب اما غیراغراق‌آمیز استفاده کن.
- انتهای متن یک جمع‌بندی تحلیلی و سناریوهای پیش رو بیاور.
- لینک یا منبع ساختگی تولید نکن؛ منابع واقعی در پیام
  توسط برنامه جداگانه اضافه می‌شوند.
- متن را به زبان فارسی بنویس.

ساختار پیشنهادی:
۱. تیتر
۲. مهم‌ترین تحولات خبری
۳. تحلیل اثر عوامل بر بازار طلا
۴. جمع‌بندی و سناریوهای پیش رو

خبرهای ورودی:

{joined_news}
""".strip()


# -----------------------------
# Cloudflare Workers AI
# -----------------------------

def analyze_news(articles):
    """Generate a Persian gold-market analysis with Cloudflare AI."""
    if not articles:
        raise ValueError("No relevant news articles were provided.")

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()

    if not account_id or not api_token:
        raise RuntimeError(
            "Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN."
        )

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{MODEL}"
    )

    prompt = build_prompt(articles)

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful financial news analyst. "
                    "Never invent facts or market data."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.3,
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Cloudflare AI HTTP {exc.code}: {error_body[:1200]}"
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Cloudflare AI request failed: {exc}"
        ) from exc

    if not result.get("success", False):
        raise RuntimeError(
            "Cloudflare AI returned an error: "
            + json.dumps(
                result.get("errors", []),
                ensure_ascii=False
            )
        )

    response_data = result.get("result", {})

    # Workers AI chat models commonly return "response".
    analysis = response_data.get("response", "")

    # Some model responses may use the OpenAI-compatible format.
    if not analysis and response_data.get("choices"):
        analysis = (
            response_data["choices"][0]
            .get("message", {})
            .get("content", "")
        )

    if not isinstance(analysis, str) or not analysis.strip():
        raise RuntimeError(
            "Cloudflare AI returned an empty or unrecognized response."
        )

    return analysis.strip()


# -----------------------------
# Standalone preview
# -----------------------------

def main():
    print("در حال دریافت خبرهای مرتبط با بازار جهانی طلا...")

    articles = fetch_news()
    selected = select_relevant_news(articles)

    print(f"تعداد خبرهای مرتبط: {len(articles)}")
    print(f"تعداد خبرهای انتخاب‌شده: {len(selected)}")

    if not selected:
        print("خبر مرتبط کافی پیدا نشد؛ تحلیل تولید نشد.")
        return

    for index, article in enumerate(selected, start=1):
        print(f"{index}. {article['title']} — {article['source']}")

    print("\nدر حال تولید تحلیل با Cloudflare AI...")
    analysis = analyze_news(selected)

    print("\n" + "=" * 50)
    print(analysis)
    print("=" * 50)


if __name__ == "__main__":
    main()
