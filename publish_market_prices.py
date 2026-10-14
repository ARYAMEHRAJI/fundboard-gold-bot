
import os
import re
import time
import html
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://gem.tgju.org"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}

PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(value):
    return str(value).translate(FA_DIGITS)


def parse_number(value):
    value = str(value).translate(PERSIAN_DIGITS)
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def fetch_page(url):
    last_error = None

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=35,
            )
            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding or "utf-8"
            )

            print(
                f"صفحه دریافت شد: {url} "
                f"(HTTP {response.status_code})"
            )

            return response.text

        except requests.RequestException as exc:
            last_error = exc
            print(
                f"خطا در دریافت صفحه، تلاش "
                f"{attempt + 1}/3: {exc}"
            )

            if attempt < 2:
                time.sleep(2 * (attempt + 1))

    raise RuntimeError(
        f"دریافت صفحه ناموفق بود: {url}"
    ) from last_error


def parse_market_page(url):
    soup = BeautifulSoup(fetch_page(url), "html.parser")
    items = []

    rows = soup.select("tr")
    print(f"تعداد ردیف‌های جدول در {url}: {len(rows)}")

    for tr in rows:
        cells = tr.find_all("td", recursive=False)

        if len(cells) < 2:
            continue

        name = cells[0].get_text(" ", strip=True)
        raw_price = cells[1].get_text(" ", strip=True)
        price = parse_number(raw_price)

        if not name or price <= 0:
            continue

        if name.lower() in {
            "عنوان", "قیمت", "قیمت زنده",
            "subject", "rates", "name", "price",
        }:
            continue

        link = tr.find("a", href=True)

        if link:
            href = urljoin(url, link["href"])
            slug = href.rstrip("/").split("/")[-1]
        else:
            href = url
            slug = re.sub(r"\W+", "-", name).strip("-")

        change = ""

        for cell in cells[1:]:
            text = cell.get_text(" ", strip=True)
            match = re.search(
                r"[-+]?\s*[\d۰-۹٠-٩,٬٫.]+\s*%",
                text,
            )

            if match:
                change = match.group(0).strip()
                break

        items.append({
            "name": name,
            "slug": slug,
            # TGJU prices are generally quoted in rials.
            "price": round(price / 10),
            "change": change,
            "url": href,
        })

    print(f"اقلام قابل استخراج از {url}: {len(items)}")
    return items


def unique_items(items):
    result = []
    seen = set()

    for item in items:
        key = item["slug"]

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def get_currency_items():
    urls = [
        f"{BASE_URL}/currency",
        "https://www.tgju.org/currency",
    ]

    for url in urls:
        try:
            items = parse_market_page(url)

            if items:
                return unique_items(items)

        except Exception as exc:
            print(f"خطای دریافت ارزها از {url}: {exc}")

    return []


def get_physical_gold_items():
    urls = [
        "https://www.tgju.org/gold-chart",
        "https://www.tgju.org/coin",
        "https://www.tgju.org/",
    ]

    items = []

    for url in urls:
        try:
            items.extend(parse_market_page(url))
        except Exception as exc:
            print(f"خطا در دریافت {url}: {exc}")

    include_words = (
        "طلا", "آبشده", "مثقال", "سکه", "شمش",
        "gold", "sekke", "parsian", "melt",
        "abshodeh", "coin",
    )

    exclude_words = (
        "صندوق", "بورس", "گواهی", "آینده",
        "نقره", "انس", "silver", "fund",
        "certificate",
    )

    selected = []

    for item in items:
        searchable = (
            item["name"] + " " + item["slug"]
        ).lower()

        if any(word in searchable for word in exclude_words):
            continue

        if any(word in searchable for word in include_words):
            selected.append(item)

    return unique_items(selected)


def build_messages(kind, items):
    if not items:
        raise RuntimeError(
            "هیچ قیمت معتبری استخراج نشد؛ "
            "برای جلوگیری از انتشار داده نامعتبر، "
            "پیام ارسال نمی‌شود."
        )

    now = datetime.now(ZoneInfo("Asia/Tehran"))
    timestamp = fa(now.strftime("%Y/%m/%d - %H:%M"))

    if kind == "currency":
        title = "💱 <b>قیمت ارزها در بازار ایران</b>"
        items.sort(key=lambda item: item["name"])
    else:
        title = "🪙 <b>قیمت طلا و سکه فیزیکی در بازار ایران</b>"
        items.sort(key=lambda item: item["name"])

    lines = [
        title,
        f"🕒 زمان تهیه گزارش: {timestamp}",
        "━━━━━━━━━━━━━━",
    ]

    for item in items:
        name = html.escape(item["name"])
        price = fa(f'{item["price"]:,}')
        change = html.escape(item["change"])

        line = f"• {name}: <b>{price} تومان</b>"

        if change:
            line += f" ({change})"

        lines.append(line)

    lines.extend([
        "━━━━━━━━━━━━━━",
        'منبع: <a href="https://www.tgju.org/">TGJU</a>',
        "",
        "<b>@FundBoard_Gold | فاندبورد طلا</b>",
        "<b>‎داشبورد سرمایه‌گذاری شما</b>",
    ])

    messages = []
    current = ""

    for line in lines:
        candidate = f"{current}\n{line}" if current else line

        if len(candidate) > 3500 and current:
            messages.append(current)
            current = line
        else:
            current = candidate

    if current:
        messages.append(current)

    return messages


def send_telegram(messages):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")

    if not token or not chat_id:
        raise RuntimeError(
            "Secretهای تلگرام در محیط اجرا تنظیم نشده‌اند."
        )

    endpoint = (
        f"https://api.telegram.org/bot{token}/sendMessage"
    )

    for message in messages:
        response = requests.post(
            endpoint,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )

        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(
                f"خطای Telegram API: {result}"
            )

        time.sleep(1)


def main():
    kind = os.environ.get(
        "MARKET_KIND", "currency"
    ).lower()

    if kind == "currency":
        items = get_currency_items()
    elif kind == "gold":
        items = get_physical_gold_items()
    else:
        raise ValueError(
            "MARKET_KIND باید currency یا gold باشد."
        )

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام استخراج‌شده: {len(items)}")

    messages = build_messages(kind, items)

    for index, message in enumerate(messages, start=1):
        print(
            f"\n--- پیام {index}/{len(messages)} ---\n"
        )
        print(message)

    publish = os.environ.get(
        "PUBLISH_TO_TELEGRAM", "false"
    ).lower() == "true"

    if publish:
        send_telegram(messages)
        print("انتشار در تلگرام موفق بود.")
    else:
        print(
            "حالت آزمایشی: پیامی به تلگرام ارسال نشد."
        )


if __name__ == "__main__":
    main()
    
