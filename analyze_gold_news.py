
import os
import re
import json
import html
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"]
API_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]

MODEL = "@cf/qwen/qwen3.8-27b"
MAX_AGE_HOURS = 18
MAX_ARTICLES = 5

QUERY = (
    '("gold price" OR "spot gold" OR "gold bullion" '
    'OR "gold market" OR "gold futures") when:1d'
)


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def get_recent_news():
    params = {
        "q": QUERY,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode(params)
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 FundBoardGoldBot/1.0"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)

    articles = []
    seen_titles = set()

    for item in root.findall("./channel/item"):
        title = clean_text(item.findtext("title", ""))
        link = item.findtext("link", "")
        source = clean_text(item.findtext("source", "نامشخص"))
        pub_date = item.findtext("pubDate", "")
        description = clean_text(
            item.findtext("description", "")
        )

        if not title or not link or not pub_date:
            continue

        try:
            published = parsedate_to_datetime(pub_date)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue

        if published < cutoff or published > now + timedelta(minutes=10):
            continue

        normalized_title = re.sub(
            r"[^a-z0-9]+", " ", title.lower()
        ).strip()

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)

        articles.append({
            "title": title,
            "source": source,
            "published_utc": published.isoformat(),
            "description": description[:900],
            "url": link,
        })

    articles.sort(
        key=lambda article: article["published_utc"],
        reverse=True,
    )

    return articles[:MAX_ARTICLES]


def analyze_news(articles):
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{ACCOUNT_ID}/ai/run/{MODEL}"
    )

    system_prompt = """
تو تحلیلگر حرفه‌ای بازار جهانی طلا برای رسانه فارسی‌زبان فاندبورد هستی.

وظیفه:
بر اساس خبرهای ورودی، یک پست تحلیلی کوتاه، دقیق و حرفه‌ای به فارسی بنویس.

قواعد الزامی:
- فقط از عنوان، منبع، زمان انتشار و توضیحات ارائه‌شده استفاده کن.
- خبر و واقعیت گزارش‌شده را از تحلیل و برداشت احتمالی جدا کن.
- از ساختن قیمت، درصد تغییر، نقل‌قول، آمار، رویداد یا علت حرکت بازار خودداری کن.
- اگر عنوان یا توضیح برای نتیجه‌گیری کافی نیست، صریح بگو اطلاعات موجود محدود است.
- اثر احتمالی بر طلا را قطعی یا تضمین‌شده معرفی نکن.
- خبرهای متناقض را پنهان نکن.
- خبرهای قدیمی را به‌عنوان خبر لحظه‌ای معرفی نکن.
- فقط منابع و پیوندهای داده‌شده را ذکر کن؛ پیوند جدید نساز.
- اگر خبرها برای تحلیل معتبر کافی نیستند، به‌جای تحلیل ساختگی بنویس:
  «خبرهای بررسی‌شده برای تهیه تحلیل معتبر کافی نیستند.»
- لحن رسانه‌ای، مستقل و مناسب کانال تلگرام فاندبورد باشد.
- از توصیه قطعی خریدوفروش خودداری کن.

قالب پیشنهادی:
🟡 فاندبورد | تحلیل اخبار بازار طلا

📰 مهم‌ترین خبر
خلاصه خبر و منبع

🔎 نکات کلیدی
نکات مستند و مرتبط با بازار

📊 برداشت تحلیلی
اثر احتمالی بر بازار طلا و عوامل نامشخص

🧭 جمع‌بندی
نتیجه‌ای محتاطانه و مبتنی بر شواهد

در پایان، پیوند خبرهای استفاده‌شده را درج کن.
اگر تنها یک خبر معتبر وجود دارد، همان را تحلیل کن و خبر دیگری نساز.
"""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "زمان فعلی UTC: "
                    + datetime.now(timezone.utc).isoformat()
                    + "\nخبرهای جمع‌آوری‌شده:\n"
                    + json.dumps(articles, ensure_ascii=False)
                ),
            },
        ],
        "max_tokens": 3000,
        "temperature": 0.2,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    if not result.get("success"):
        raise RuntimeError(
            "Cloudflare returned an unsuccessful response."
        )

    
choices = result.get("result", {}).get("choices", [])

if not choices:
    raise RuntimeError(
        "No analysis was returned. Response: "
        + json.dumps(result.get("result", {}), ensure_ascii=False)[:2000]
    )

choice = choices[0]
message = choice.get("message") or {}
content = message.get("content")

if not isinstance(content, str) or not content.strip():
    print("Model finish reason:", choice.get("finish_reason"))
    print("Model stop reason:", choice.get("stop_reason"))
    print("Returned fields:", list(message.keys()))
    print(
        "Model response details:",
        json.dumps(
            result.get("result", {}),
            ensure_ascii=False
        )[:3000]
    )
    raise RuntimeError(
        "The model returned no publishable text. "
        "See response details above."
    )

return content.strip()



def main():
    print("=== FUNDBOARD GOLD NEWS ANALYSIS TEST ===")

    articles = get_recent_news()

    print("Fresh articles found:", len(articles))

    if not articles:
        print(
            "No sufficiently recent articles found. "
            "No analysis generated."
        )
        return

    for number, article in enumerate(articles, start=1):
        print(f"{number}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Published UTC: {article['published_utc']}")

    print("\n=== AI ANALYSIS ===\n")
    print(analyze_news(articles))
    print("\n=== END OF TEST ===")


if __name__ == "__main__":
    main()
  
