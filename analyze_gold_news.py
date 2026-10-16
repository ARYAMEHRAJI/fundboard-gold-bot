
import os
import re
import json
import time
import html
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


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

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    + urllib.parse.urlencode({
        "q": NEWS_QUERY,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
)


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", str(value))
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value):
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def get_source_name(item):
    source = item.find("source")
    if source is not None and source.text:
        return clean_text(source.text)

    link = item.findtext("link", "")
    try:
        return urllib.parse.urlparse(link).netloc.replace("www.", "")
    except Exception:
        return "Unknown source"


def is_relevant_article(article):
    title = article.get("title", "").lower()
    summary = article.get("summary", "").lower()
    text = title + " " + summary

    gold_terms = (
        "gold", "bullion", "xau", "precious metal",
        "gold price", "gold futures"
    )
    return any(term in text for term in gold_terms)


def fetch_news():
    request = urllib.request.Request(
        GOOGLE_NEWS_URL,
        headers={"User-Agent": "Mozilla/5.0 FundBoardGoldBot/1.0"}
    )

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"Fetching recent news (attempt {attempt}/{MAX_ATTEMPTS})...")

            with urllib.request.urlopen(request, timeout=45) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            articles = []

            for item in root.findall(".//item"):
                title = clean_text(item.findtext("title", ""))
                link = clean_text(item.findtext("link", ""))
                summary = clean_text(item.findtext("description", ""))
                published_raw = item.findtext("pubDate", "")
                published = parse_date(published_raw)

                article = {
                    "title": title,
                    "link": link,
                    "summary": summary[:1800],
                    "source": get_source_name(item),
                    "published": published,
                    "published_raw": published_raw,
                }

                if title and link and is_relevant_article(article):
                    articles.append(article)

            print(f"Relevant articles fetched: {len(articles)}")
            return articles

        except Exception as exc:
            last_error = exc
            print(f"News fetch failed: {exc}")

            if attempt < MAX_ATTEMPTS:
                time.sleep(3 * attempt)

    raise RuntimeError(f"Could not fetch news: {last_error}")


def select_relevant_news(articles):
    """Keep only recent, dated articles with valid web links.

    Missing or unparseable publication dates are rejected rather than treated
    as fresh. Publisher diversity is prioritized before filling remaining slots.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=36)
    filtered = []
    seen_links = set()
    seen_titles = set()

    for article in articles:
        published = article.get("published")
        if not isinstance(published, datetime):
            continue

        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        else:
            published = published.astimezone(timezone.utc)

        # Reject stale items and implausible future timestamps.
        if published < cutoff or published > now + timedelta(minutes=10):
            continue

        link = str(article.get("link", "")).strip()
        parsed_link = urllib.parse.urlparse(link)
        if parsed_link.scheme not in ("http", "https") or not parsed_link.netloc:
            continue

        title = clean_text(article.get("title", ""))
        title_key = re.sub(r"[^a-z0-9]+", "", title.lower())
        if not title or not title_key or link in seen_links or title_key in seen_titles:
            continue

        source = clean_text(article.get("source", ""))
        if not source or source.lower() in {"unknown", "unknown source", "n/a"}:
            source = parsed_link.hostname or "Unknown source"

        normalized = dict(article)
        normalized["title"] = title
        normalized["link"] = link
        normalized["published"] = published
        normalized["source"] = source

        seen_links.add(link)
        seen_titles.add(title_key)
        filtered.append(normalized)

    # Prioritize distinct publishers to reduce duplicate coverage.
    selected = []
    selected_links = set()
    selected_sources = set()

    for article in filtered:
        source = article.get("source", "Unknown source").strip().lower()
        if source and source != "unknown source" and source not in selected_sources:
            selected.append(article)
            selected_sources.add(source)
            selected_links.add(article["link"])

        if len(selected) >= MAX_ARTICLES_FOR_ANALYSIS:
            break

    if len(selected) < MAX_ARTICLES_FOR_ANALYSIS:
        for article in filtered:
            if article["link"] not in selected_links:
                selected.append(article)
                selected_links.add(article["link"])

            if len(selected) >= MAX_ARTICLES_FOR_ANALYSIS:
                break

    print(f"Relevant articles after freshness/link checks: {len(filtered)}")
    print(f"Selected articles: {len(selected)}")
    print(f"Distinct sources: {len(set(a.get('source', '').strip().lower() for a in selected if a.get('source')))}")

    return selected

def build_prompt(articles):
    news_items = []

    for index, article in enumerate(articles, start=1):
        published = article.get("published")
        published_text = (
            published.strftime("%Y-%m-%d %H:%M UTC")
            if published else article.get("published_raw", "Unknown")
        )

        news_items.append(
            f"{index}. Headline: {article.get('title', '')}\n"
            f"Publisher: {article.get('source', '')}\n"
            f"Published: {published_text}\n"
            f"Summary: {article.get('summary', '')}"
        )

    news_text = "\n\n".join(news_items)

    return f"""
بر اساس خبرهای زیر، یک تحلیل حرفه‌ای، کوتاه و قابل انتشار برای کانال
تلگرامی «فاندبورد طلا» به زبان فارسی بنویس.

قواعد الزامی:
1. خط اول، تیتر اصلی باشد؛ جذاب، دقیق و همراه یک ایموجی مرتبط مثل 🟡، 🥇،
📈، 📉 یا ⚠️. تیتر کوتاه و خبری باشد.
2. بعد از تیتر، یک خط خالی بگذار.
3. متن را در چند پاراگراف کوتاه بنویس و برای شروع بخش‌های مهم از ایموجی
مرتبط مانند 🌍، 💵، 🏦، 📊 و 🔎 استفاده کن.
4. خبرها را تحلیل کن؛ صرفاً تیترها را پشت سر هم تکرار نکن.
5. اثر احتمالی اخبار بر قیمت جهانی طلا و عوامل اثرگذار مانند دلار آمریکا،
بازده اوراق، نرخ بهره، تورم و ریسک‌های ژئوپلیتیک را توضیح بده؛ فقط وقتی
که خبرهای ارائه‌شده واقعاً از آن عوامل پشتیبانی می‌کنند.
6. هیچ عدد، قیمت، تاریخ، نقل‌قول، پیش‌بینی یا رویدادی را از خودت نساز.
اگر اطلاعات کافی برای تأیید یک ادعا وجود ندارد، آن را قطعی بیان نکن.
7. میان واقعیت گزارش‌شده و برداشت تحلیلی تفاوت بگذار. از قطعیت بی‌مورد
و توصیه مستقیم خرید یا فروش خودداری کن.
8. در پایان، یک جمع‌بندی کوتاه با عنوان «🧭 جمع‌بندی فاندبورد» اضافه کن.
9. هیچ فهرست منابع، لینک، امضای کانال، مقدمه درباره روش کار یا توضیح
اضافی خارج از متن پست ننویس. امضای کانال توسط برنامه اضافه می‌شود.
10. خروجی فقط متن نهایی فارسی باشد. از Markdown، ستاره، هشتگ و کد HTML
استفاده نکن؛ قالب‌بندی تیتر و امضا توسط برنامه انجام خواهد شد.

خبرهای ورودی:
{news_text}
""".strip()


def extract_analysis(data):
    if not isinstance(data, dict):
        return ""

    result = data.get("result", data)
    if not isinstance(result, dict):
        return ""

    choices = result.get("choices", [])
    if isinstance(choices, list) and choices:
        choice = choices[0] or {}
        message = choice.get("message", {}) or {}
        content = message.get("content")

        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
            if parts:
                return "\n".join(parts).strip()

    for key in ("response", "output_text", "content", "text"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def analyze_news(articles):
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()

    if not account_id or not api_token:
        raise RuntimeError(
            "Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN secret."
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
                    "تو تحلیلگر اخبار بازار جهانی طلا هستی. "
                    "فقط گزارش نهایی فارسی را مطابق دستور کاربر بنویس. "
                    "هیچ واقعیت، قیمت یا رویدادی را جعل نکن."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 3000,
        "reasoning_effort": "low",
        "temperature": 0.3,
    }

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"Calling Cloudflare AI (attempt {attempt}/{MAX_ATTEMPTS}, "
            "reasoning_effort=low)..."
        )

        try:
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT
            ) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )

            if response_data.get("success") is False:
                raise RuntimeError(
                    "Cloudflare API error: "
                    + json.dumps(
                        response_data.get("errors", []),
                        ensure_ascii=False
                    )
                )

            analysis = extract_analysis(response_data)

            if analysis:
                print(
                    "Analysis generated successfully: "
                    f"{len(analysis)} characters."
                )
                return analysis

            last_error = RuntimeError(
                "Cloudflare returned no message content."
            )

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(
                f"Cloudflare HTTP {exc.code}: {error_body[:1500]}"
            )

        except Exception as exc:
            last_error = exc

        print(f"AI attempt failed: {last_error}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(5 * attempt)

    raise RuntimeError(f"AI analysis failed after retries: {last_error}")


def main():
    print("FundBoard Gold News Analyzer")
    articles = select_relevant_news(fetch_news())

    if len(articles) < 2:
        raise RuntimeError(
            "Not enough relevant articles to generate a reliable analysis."
        )

    analysis = analyze_news(articles)

    print("\nGenerated message preview:\n")
    print(analysis)
    print("\nSources selected:")
    for article in articles:
        print(f"• {article.get('source', 'Unknown')}: {article.get('title', '')}")


if __name__ == "__main__":
    main()
