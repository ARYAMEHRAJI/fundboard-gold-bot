
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

REQUEST_TIMEOUT = 180
MAX_ATTEMPTS = 3
MAX_ARTICLES_FOR_ANALYSIS = 8

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


# ============================================================
# Text utilities
# ============================================================

def clean_text(value):
    """Remove HTML tags and normalize whitespace."""
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def get_source_name(article):
    """Return a readable publisher name."""
    source = article.get("source", "")

    if isinstance(source, dict):
        source = source.get("title", "")

    if source:
        return clean_text(source)

    link = article.get("link", "")

    try:
        return urlparse(link).netloc.replace("www.", "")
    except Exception:
        return "Unknown"


def parse_date(value):
    """Parse an RSS publication date into a timezone-aware datetime."""
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
    """Filter out articles that are not meaningfully about gold."""
    title = clean_text(article.get("title", "")).lower()
    summary = clean_text(article.get("summary", "")).lower()
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
        "gold jewelry",
        "gold jewellery",
        "golden retriever",
    )

    if any(term in text for term in irrelevant_terms):
        return False

    return True


def fetch_news():
    """Fetch recent gold-market news from Google News RSS."""
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

            print(f"Relevant articles fetched: {len(articles)}")
            return articles

        except Exception as exc:
            last_error = exc

            print(
                f"News RSS attempt {attempt}/"
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
    """
    Keep recent articles, prioritize distinct publishers,
    and avoid duplicate links and headlines.
    """
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

    # Prefer the newest articles when publication dates are available.
    candidates.sort(
        key=lambda item: (
            parse_date(item.get("published", "")) is not None,
            parse_date(item.get("published", ""))
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    # First select one article per source.
    selected = []
    selected_links = set()
    selected_sources = set()

    for article in candidates:
        source = article.get("source", "Unknown").lower()

        if source not in selected_sources:
            selected.append(article)
            selected_sources.add(source)
            selected_links.add(article["link"])

        if len(selected) >= MAX_ARTICLES_FOR_ANALYSIS:
            break

    # Fill remaining places if there are not enough distinct sources.
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
    """Prepare the Persian gold-market analysis prompt."""
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
نقش تو: تحلیلگر حرفه‌ای بازار جهانی طلا برای رسانه مالی
«فاندبورد | FundBoard».

بر اساس خبرهای زیر، یک گزارش تحلیلی دقیق و روان به زبان فارسی
برای انتشار در کانال تلگرام بنویس.

خبرها:
{news_text}

قواعد مهم:
- فقط از اطلاعات موجود در خبرها استفاده کن.
- هیچ قیمت، درصد تغییر، پیش‌بینی عددی یا نقل‌قولی را جعل نکن.
- اگر داده کافی وجود ندارد، صریحاً از قطعیت پرهیز کن.
- بین واقعیت خبری و برداشت تحلیلی تفاوت بگذار.
- تأثیر احتمالی دلار آمریکا، نرخ بهره فدرال رزرو،
  بازده اوراق خزانه‌داری، تورم و ریسک‌های ژئوپلیتیکی را
  فقط در صورت ارتباط با خبرها توضیح بده.
- اخبار متناقض را پنهان نکن.
- از توصیه قطعی خرید یا فروش خودداری کن.
- متن را خلاصه، حرفه‌ای، مستقل و مناسب تلگرام بنویس.
- تیتر جذاب و تحلیلی داشته باش.
- از مقدمه‌های کلیشه‌ای و تکرار یک مطلب پرهیز کن.
- در انتها یک جمع‌بندی کوتاه با عنوان «جمع‌بندی فاندبورد» بیاور.
- فهرست منابع و لینک‌ها را تولید نکن؛ برنامه انتشار آن‌ها را
  جداگانه اضافه می‌کند.
- خروجی را فقط به زبان فارسی و بدون توضیح درباره فرایند تولید
  متن ارائه بده.
"""


# ============================================================
# Cloudflare AI response handling
# ============================================================

def extract_analysis(data):
    """Extract generated text from common Cloudflare response shapes."""
    if not isinstance(data, dict):
        return ""

    result = data.get("result")

    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        # Common Workers AI text-generation response.
        response = result.get("response")

        if isinstance(response, str) and response.strip():
            return response.strip()

        # Alternative text fields.
        for key in ("output_text", "generated_text", "text"):
            value = result.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        # Chat-completion style response.
        choices = result.get("choices")

        if isinstance(choices, list) and choices:
            first = choices[0]

            if isinstance(first, dict):
                message = first.get("message", {})

                if isinstance(message, dict):
                    content = message.get("content")

                    if isinstance(content, str) and content.strip():
                        return content.strip()

                text_value = first.get("text")

                if (
                    isinstance(text_value, str)
                    and text_value.strip()
                ):
                    return text_value.strip()

    # Some responses may expose choices at the top level.
    choices = data.get("choices")

    if isinstance(choices, list) and choices:
        first = choices[0]

        if isinstance(first, dict):
            message = first.get("message", {})

            if isinstance(message, dict):
                content = message.get("content")

                if isinstance(content, str) and content.strip():
                    return content.strip()

    return ""


def analyze_news(articles):
    """Generate the analysis with retries for temporary failures."""
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
                    "تو تحلیلگر بازار جهانی طلا هستی. "
                    "فقط به فارسی و بر اساس داده‌های ارائه‌شده "
                    "پاسخ بده و اطلاعات جعل نکن."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": 1600,
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
                f"timeout={REQUEST_TIMEOUT}s)..."
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
                    "Cloudflare returned invalid JSON. "
                    f"Response preview: {response_body[:1200]}"
                ) from exc

            if not isinstance(data, dict):
                raise RuntimeError(
                    "Cloudflare returned an unexpected response "
                    f"type: {type(data).__name__}"
                )

            if data.get("success") is False:
                errors = data.get("errors", [])
                raise RuntimeError(
                    "Cloudflare API reported failure: "
                    + json.dumps(
                        errors,
                        ensure_ascii=False,
                    )[:1500]
                )

            analysis = extract_analysis(data)

            if analysis:
                print(
                    f"Analysis generated successfully "
                    f"({len(analysis)} characters)."
                )
                return analysis

            raise RuntimeError(
                "Cloudflare AI returned an empty or "
                "unrecognized response. Response preview: "
                + json.dumps(
                    data,
                    ensure_ascii=False,
                )[:1500]
            )

        except urllib.error.HTTPError as exc:
            error_body = ""

            try:
                error_body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                pass

            last_error = RuntimeError(
                f"Cloudflare HTTP {exc.code}: "
                f"{error_body[:1500]}"
            )

            print(
                f"Cloudflare HTTP error on attempt "
                f"{attempt}/{MAX_ATTEMPTS}: {last_error}"
            )

            # Retry only errors that may be temporary.
            if exc.code not in (408, 425, 429, 500, 502, 503, 504):
                raise last_error from exc

        except (
            TimeoutError,
            urllib.error.URLError,
            ConnectionError,
        ) as exc:
            last_error = exc

            print(
                f"Cloudflare network/timeout error on attempt "
                f"{attempt}/{MAX_ATTEMPTS}: {exc}"
            )

        except RuntimeError as exc:
            last_error = exc

            print(
                f"Cloudflare response error on attempt "
                f"{attempt}/{MAX_ATTEMPTS}: {exc}"
            )

            # Response parsing/API errors usually will not improve
            # with a retry, so stop here.
            raise

        if attempt < MAX_ATTEMPTS:
            delay = 10 * attempt
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)

    raise RuntimeError(
        f"Cloudflare AI request failed after "
        f"{MAX_ATTEMPTS} attempts. Last error: {last_error}"
    )


# ============================================================
# Local preview
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
