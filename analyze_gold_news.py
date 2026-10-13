
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
from urllib.parse import urlparse


# =========================================================
# Configuration
# =========================================================

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


# =========================================================
# Text utilities
# =========================================================

def clean_text(value):
    """Remove HTML tags and normalize whitespace."""
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def is_relevant_article(article):
    """Identify news relevant to gold and its market drivers."""
    title = clean_text(article.get("title", "")).lower()
    description = clean_text(
        article.get("description", "")
    ).lower()

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

    # Gold-specific headlines are preferred.
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


# =========================================================
# Google News RSS
# =========================================================

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
        with urllib.request.urlopen(
            request,
            timeout=25,
        ) as response:
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

        source = ""
        if source_element is not None:
            source = clean_text(source_element.text or "")

        if not title or not link:
            continue

        if link in seen_links:
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


# =========================================================
# Article selection
# =========================================================

def select_relevant_news(
    articles,
    limit=MAX_ARTICLES_FOR_ANALYSIS,
):
    """Prioritize gold headlines and reduce duplicate titles."""
    gold_terms = (
        "gold",
        "bullion",
        "xau",
        "precious metal",
    )

    ranked = sorted(
        articles,
        key=lambda article: (
            not any(
                term in article.get("title", "").lower()
                for term in gold_terms
            ),
            article.get("published", ""),
        ),
    )

    selected = []
    seen_titles = set()

    for article in ranked:
        normalized_title = re.sub(
            r"\W+",
            " ",
            article.get("title", "").lower(),
        ).strip()

        if not normalized_title:
            continue

        if normalized_title in seen_titles:
            continue

        selected.append(article)
        seen_titles.add(normalized_title)

        if len(selected) >= limit:
            break

    return selected


# =========================================================
# Prompt construction
# =========================================================

def build_prompt(articles):
    """Build a Persian financial analysis prompt from RSS news."""
    news_items = []

    for index, article in enumerate(articles, start=1):
        news_items.append(
            f"{index}. عنوان: {article.get('title', '')}\n"
            f"منبع: {article.get('source', '')}\n"
            f"زمان انتشار: "
            f"{article.get('published', 'نامشخص')}\n"
            f"خلاصه خبر: "
            f"{article.get('description', '')[:900]}"
        )

    news_text = "\n\n".join(news_items)

    return f"""
تو تحلیلگر بازار جهانی طلا برای رسانه فاندبورد هستی.

بر اساس خبرهای زیر، یک تحلیل فارسی دقیق، روان و مستقل
برای انتشار در کانال تلگرامی تهیه کن.

قواعد:
- فقط بر اساس اطلاعات موجود در خبرها تحلیل کن.
- قیمت لحظه‌ای، درصد تغییر، آمار یا نقل‌قولی را که در
  داده‌ها وجود ندارد، اختراع نکن.
- میان واقعیت خبری، برداشت تحلیلی و سناریوی احتمالی تفاوت بگذار.
- اثر نرخ بهره آمریکا، دلار، بازده اوراق خزانه، تورم و
  ریسک‌های ژئوپلیتیک را در صورت ارتباط توضیح بده.
- در نبود شواهد کافی، عدم قطعیت را صریح بیان کن.
- پیش‌بینی قطعی قیمت و توصیه مستقیم خرید یا فروش نده.
- خبرهای تکراری را ادغام کن.
- تیتر جذاب اما غیراغراق‌آمیز انتخاب کن.
- متن کاربردی، مختصر و مناسب تلگرام باشد.
- در پایان، جمع‌بندی و سناریوهای پیش رو را بنویس.
- منبع یا لینک ساختگی نساز؛ برنامه منابع واقعی را جداگانه اضافه می‌کند.

ساختار:
۱. تیتر
۲. مهم‌ترین تحولات خبری
۳. تحلیل اثر عوامل بر بازار طلا
۴. جمع‌بندی و سناریوهای پیش رو

خبرهای ورودی:

{news_text}
""".strip()


# =========================================================
# Cloudflare Workers AI
# =========================================================

def extract_analysis(result):
    """Extract text from common Cloudflare AI response formats."""
    if not isinstance(result, dict):
        return ""

    response_data = result.get("result", {})

    if isinstance(response_data, str):
        return response_data.strip()

    if not isinstance(response_data, dict):
        return ""

    # Standard Workers AI response
    analysis = response_data.get("response")

    if isinstance(analysis, str) and analysis.strip():
        return analysis.strip()

    # OpenAI-compatible response
    choices = response_data.get("choices", [])

    if isinstance(choices, list) and choices:
        first_choice = choices[0]

        if isinstance(first_choice, dict):
            message = first_choice.get("message", {})

            if isinstance(message, dict):
                content = message.get("content")

                if isinstance(content, str) and content.strip():
                    return content.strip()

                if isinstance(content, list):
                    parts = []

                    for item in content:
                        if isinstance(item, dict):
                            text_part = item.get("text")
                            if text_part:
                                parts.append(str(text_part))
                        elif isinstance(item, str):
                            parts.append(item)

                    if parts:
                        return "\n".join(parts).strip()

            # Some responses put generated text here.
            text_value = first_choice.get("text")

            if isinstance(text_value, str) and text_value.strip():
                return text_value.strip()

    # Other possible response fields
    for key in ("generated_text", "output_text", "text"):
        value = response_data.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    output = response_data.get("output")

    if isinstance(output, str) and output.strip():
        return output.strip()

    if isinstance(output, dict):
        for key in ("text", "response", "content"):
            value = output.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def analyze_news(articles):
    """Generate Persian analysis using Cloudflare Workers AI."""
    if not articles:
        raise ValueError(
            "No relevant news articles were provided."
        )

    account_id = os.getenv(
        "CLOUDFLARE_ACCOUNT_ID", ""
    ).strip()

    api_token = os.getenv(
        "CLOUDFLARE_API_TOKEN", ""
    ).strip()

    if not account_id or not api_token:
        raise RuntimeError(
            "Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN."
        )

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{MODEL}"
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful financial news analyst. "
                    "Never invent facts, prices, or market data. "
                    "Write the final answer in Persian."
                ),
            },
            {
                "role": "user",
                "content": build_prompt(articles),
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
        with urllib.request.urlopen(
            request,
            timeout=90,
        ) as response:
            raw_response = response.read().decode(
                "utf-8",
                errors="replace",
            )

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Cloudflare AI HTTP {exc.code}: "
            f"{error_body[:2000]}"
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Cloudflare AI request failed: {exc}"
        ) from exc

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Cloudflare returned invalid JSON: "
            f"{raw_response[:2000]}"
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError(
            "Unexpected Cloudflare response type: "
            f"{type(result).__name__}"
        )

    if not result.get("success", False):
        raise RuntimeError(
            "Cloudflare AI returned an API error: "
            + json.dumps(
                {
                    "errors": result.get("errors", []),
                    "messages": result.get("messages", []),
                },
                ensure_ascii=False,
                default=str,
            )[:3000]
        )

    analysis = extract_analysis(result)

    if not analysis:
        # Print useful diagnostic details without exposing
        # the API token or other secret values.
        diagnostic = {
            "result_keys": (
                list(result.get("result", {}).keys())
                if isinstance(result.get("result"), dict)
                else str(type(result.get("result")).__name__)
            ),
            "result_preview": result.get("result"),
            "messages": result.get("messages", []),
            "errors": result.get("errors", []),
        }

        raise RuntimeError(
            "Could not extract analysis from Cloudflare response. "
            "Diagnostic: "
            + json.dumps(
                diagnostic,
                ensure_ascii=False,
                default=str,
            )[:3000]
        )

    return analysis


# =========================================================
# Standalone preview
# =========================================================

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
        print(
            f"{index}. {article['title']} "
            f"— {article['source']}"
        )

    print("\nدر حال تولید تحلیل با Cloudflare AI...")

    analysis = analyze_news(selected)

    print("\n" + "=" * 50)
    print(analysis)
    print("=" * 50)


if __name__ == "__main__":
    main()
