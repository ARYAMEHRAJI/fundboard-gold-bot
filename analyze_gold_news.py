
import os
import re
import html
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse


# ============================================================
# Configuration
# ============================================================

NEWS_QUERY = (
    '"spot gold" OR "gold futures" OR "gold bullion" OR '
    '"XAU/USD" OR ("gold price" AND '
    '(Fed OR inflation OR dollar OR "Treasury yields" '
    'OR "central bank" OR geopolitics)) when:1d'
)

MODEL = "@cf/qwen/qwen3.8-27b"

REQUEST_TIMEOUT = 120
MAX_ATTEMPTS = 3
MAX_ARTICLES_FOR_ANALYSIS = 8

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


# ============================================================
# Text utilities
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def get_source_name(article):
    source = article.get("source", "")

    if isinstance(source, dict):
        source = source.get("title", "")

    if source:
        return clean_text(source)

    try:
        return urlparse(
            article.get("link", "")
        ).netloc.replace("www.", "")
    except Exception:
        return "Unknown"


def parse_date(value):
    if not value:
        return None

    try:
        result = parsedate_to_datetime(value)

        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result.astimezone(timezone.utc)

    except Exception:
        return None


# ============================================================
# News retrieval
# ============================================================

def is_relevant_article(article):
    title = clean_text(
        article.get("title", "")
    ).lower()

    summary = clean_text(
        article.get("summary", "")
    ).lower()

    text = f"{title} {summary}"

    gold_terms = (
        "gold",
        "bullion",
        "xau",
        "precious metal",
        "precious metals",
    )

    if not any(term in text for term in gold_terms):
        return False

    irrelevant_terms = (
        "golden state warriors",
        "golden globes",
        "gold medal",
        "gold award",
        "golden retriever",
    )

    if any(term in text for term in irrelevant_terms):
        return False

    return True


def fetch_news():
    params = {
        "q": NEWS_QUERY,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    url = (
        GOOGLE_NEWS_RSS
        + "?"
        + urllib.parse.urlencode(params)
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; FundBoardGoldBot/1.0)"
            )
        },
    )

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                request,
                timeout=45,
            ) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            articles = []

            for item in root.findall(".//item"):
                title = clean_text(
                    item.findtext("title", "")
                )

                link = clean_text(
                    item.findtext("link", "")
                )

                summary = clean_text(
                    item.findtext("description", "")
                )

                published = clean_text(
                    item.findtext("pubDate", "")
                )

                source_element = item.find("source")

                source = (
                    clean_text(source_element.text)
                    if source_element is not None
                    else ""
                )

                if not title or not link:
                    continue

                article = {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                    "source": source,
                }

                if is_relevant_article(article):
                    articles.append(article)

            print(
                f"Relevant articles fetched: {len(articles)}"
            )

            return articles

        except Exception as exc:
            last_error = exc

            print(
                f"RSS attempt {attempt}/"
                f"{MAX_ATTEMPTS} failed: {exc}"
            )

            if attempt < MAX_ATTEMPTS:
                time.sleep(3 * attempt)

    raise RuntimeError(
        f"Could not retrieve news RSS: {last_error}"
    )


# ============================================================
# Article selection
# ============================================================

def select_relevant_news(articles):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=36)

    candidates = []
    seen_links = set()
    seen_titles = set()

    for article in articles:
        link = article.get("link", "").strip()
        title = clean_text(article.get("title", ""))

        if not link or not title:
            continue

        normalized_link = link.rstrip("/").lower()

        normalized_title = re.sub(
            r"[^a-z0-9]+",
            "",
            title.lower(),
        )

        if normalized_link in seen_links:
            continue

        if normalized_title in seen_titles:
            continue

        seen_links.add(normalized_link)
        seen_titles.add(normalized_title)

        published_date = parse_date(
            article.get("published", "")
        )

        if published_date and published_date < cutoff:
            continue

        article["source"] = get_source_name(article)

        candidates.append(article)

    candidates.sort(
        key=lambda item: (
            parse_date(item.get("published", "")) is not None,
            parse_date(item.get("published", ""))
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    selected = []
    selected_links = set()
    selected_sources = set()

    # First pass: prefer different publishers.
    for article in candidates:
        source = article.get(
            "source", "Unknown"
        ).lower()

        if source not in selected_sources:
            selected.append(article)
            selected_sources.add(source)
            selected_links.add(article["link"])

        if len(selected) >= MAX_ARTICLES_FOR_ANALYSIS:
            break

    # Second pass: fill remaining places.
    if len(selected) < MAX_ARTICLES_FOR_ANALYSIS:
        for article in candidates:
            if article["link"] in selected_links:
                continue

            selected.append(article)
            selected_links.add(article["link"])

            if len(selected) >= MAX_ARTICLES_FOR_ANALYSIS:
                break

    sources = {
        article.get("source", "Unknown")
        for article in selected
    }

    print(f"Selected articles: {len(selected)}")
    print(f"Distinct sources: {len(sources)}")

    return selected


# ============================================================
# Prompt construction
# ============================================================

def build_prompt(articles):
    article_blocks = []

    for index, article in enumerate(articles, start=1):
        article_blocks.append(
            f"""
خبر {index}
عنوان: {article.get("title", "")}
منبع: {article.get("source", "")}
زمان انتشار: {article.get("published", "")}
خلاصه: {article.get("summary", "")}
"""
        )

    news_text = "\n".join(article_blocks)

    return f"""
بر اساس خبرهای زیر، یک گزارش تحلیلی دقیق و روان به زبان فارسی
برای انتشار در کانال تلگرام «فاندبورد | FundBoard» بنویس.

خبرها:
{news_text}

دستورالعمل:
- فقط از اطلاعات ارائه‌شده استفاده کن.
- قیمت، درصد، نقل‌قول یا آمار جدید جعل نکن.
- بین واقعیت خبری و برداشت تحلیلی تفاوت بگذار.
- تأثیر احتمالی دلار آمریکا، نرخ بهره فدرال رزرو،
  بازده اوراق خزانه‌داری، تورم و ریسک‌های ژئوپلیتیکی را
  فقط در صورت ارتباط با خبرها توضیح بده.
- خبرهای متناقض را پنهان نکن.
- از توصیه قطعی خرید یا فروش خودداری کن.
- متن را حرفه‌ای، خلاصه و مناسب تلگرام بنویس.
- یک تیتر جذاب و تحلیلی انتخاب کن.
- از تکرار و مقدمه‌های کلیشه‌ای پرهیز کن.
- در انتها بخشی با عنوان «جمع‌بندی فاندبورد» بیاور.
- منابع و لینک‌ها را در متن تولید نکن؛ برنامه انتشار جداگانه
  لینک منابع را اضافه می‌کند.
- هیچ توضیحی درباره مراحل استدلال یا نحوه تولید متن ننویس.
- فقط متن نهایی قابل انتشار را برگردان.
"""


# ============================================================
# Response parsing
# ============================================================

def extract_analysis(data):
    if not isinstance(data, dict):
        return ""

    result = data.get("result", data)

    if isinstance(result, str):
        return result.strip()

    if not isinstance(result, dict):
        return ""

    choices = result.get("choices", [])

    if isinstance(choices, list) and choices:
        for choice in choices:
            if not isinstance(choice, dict):
                continue

            message = choice.get("message", {})

            if isinstance(message, dict):
                content = message.get("content")

                if isinstance(content, str) and content.strip():
                    return content.strip()

                # Some APIs return content as text blocks.
                if isinstance(content, list):
                    text_parts = []

                    for part in content:
                        if (
                            isinstance(part, dict)
                            and isinstance(part.get("text"), str)
                        ):
                            text_parts.append(part["text"])

                    combined = "\n".join(text_parts).strip()

                    if combined:
                        return combined

            text_value = choice.get("text")

            if isinstance(text_value, str) and text_value.strip():
                return text_value.strip()

    # Handle other common response formats.
    for key in ("response", "output_text", "generated_text", "text"):
        value = result.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # Intentionally do not use the "reasoning" field as published text.
    return ""


# ============================================================
# Cloudflare AI
# ============================================================

def analyze_news(articles):
    account_id = os.environ.get(
        "CLOUDFLARE_ACCOUNT_ID", ""
    ).strip()

    api_token = os.environ.get(
        "CLOUDFLARE_API_TOKEN", ""
    ).strip()

    if not account_id or not api_token:
        raise RuntimeError(
            "Missing CLOUDFLARE_ACCOUNT_ID or "
            "CLOUDFLARE_API_TOKEN environment variable."
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
                    "تو تحلیلگر حرفه‌ای بازار جهانی طلا هستی. "
                    "یک گزارش نهایی فارسی تولید کن. "
                    "پاسخ نهایی باید در فیلد محتوای پیام باشد؛ "
                    "نه صرفاً در بخش استدلال داخلی. "
                    "از جعل اطلاعات خودداری کن."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_completion_tokens": 3000,
        "reasoning_effort": "low",
        "temperature": 0.3,
    }

    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "User-Agent": "FundBoardGoldBot/1.0",
            },
            method="POST",
        )

        try:
            print(
                f"Calling Cloudflare AI "
                f"(attempt {attempt}/{MAX_ATTEMPTS}, "
                f"reasoning_effort=low)..."
            )

            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response_body = response.read().decode(
                    "utf-8",
                    errors="replace",
                )

            try:
                data = json.loads(response_body)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Cloudflare returned invalid JSON: "
                    + response_body[:1200]
                ) from exc

            if not isinstance(data, dict):
                raise RuntimeError(
                    "Unexpected Cloudflare response type."
                )

            if data.get("success") is False:
                raise RuntimeError(
                    "Cloudflare API failure: "
                    + json.dumps(
                        data.get("errors", []),
                        ensure_ascii=False,
                    )[:1500]
                )

            analysis = extract_analysis(data)

            if analysis:
                print(
                    "Analysis generated successfully: "
                    f"{len(analysis)} characters."
                )

                return analysis

            last_error = RuntimeError(
                "Cloudflare returned no final text. "
                "Response preview: "
                + json.dumps(
                    data,
                    ensure_ascii=False,
                )[:2000]
            )

            print(
                f"Empty response on attempt "
                f"{attempt}/{MAX_ATTEMPTS}."
            )
            print(str(last_error))

        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                error_body = ""

            last_error = RuntimeError(
                f"Cloudflare HTTP {exc.code}: "
                f"{error_body[:1500]}"
            )

            print(str(last_error))

            if exc.code not in (
                408, 425, 429, 500, 502, 503, 504
            ):
                raise last_error from exc

        except (
            TimeoutError,
            urllib.error.URLError,
            ConnectionError,
        ) as exc:
            last_error = exc

            print(
                f"Network/timeout error on attempt "
                f"{attempt}/{MAX_ATTEMPTS}: {exc}"
            )

        except RuntimeError as exc:
            last_error = exc
            print(str(exc))

        if attempt < MAX_ATTEMPTS:
            delay = 5 * attempt
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)

    raise RuntimeError(
        f"Cloudflare AI failed after {MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )


# ============================================================
# Standalone preview
# ============================================================

def main():
    print("FundBoard Gold News Analyzer")
    print("Fetching recent gold-market news...")

    articles = fetch_news()
    selected_articles = select_relevant_news(articles)

    if not selected_articles:
        raise RuntimeError(
            "No relevant recent gold news was found."
        )

    print("Generating Persian analysis...")

    analysis = analyze_news(selected_articles)

    print("\n" + "=" * 60)
    print(analysis)
    print("=" * 60)


if __name__ == "__main__":
    main()
