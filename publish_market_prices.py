
import os
import re
import time
import html
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.tgju.org"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
    )
}
PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(value):
    return str(value).translate(FA_DIGITS)


def fetch_page(url):
    last_error = None

    for attempt in range(3):
        try:
            response = requests.get(
                url, headers=HEADERS, timeout=35
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"دریافت داده ناموفق بود: {url}") from last_error


def parse_number(value):
    value = value.translate(PERSIAN_DIGITS)
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def parse_market_page(url):
    soup = BeautifulSoup(fetch_page(url), "html.parser")
    items = []

    for tr in soup.select("tr"):
        link = tr.find("a", href=re.compile(r"/profile/"))
        cells = tr.find_all(["td", "th"], recursive=False)

        if not link or len(cells) < 2:
            continue

        name = link.get_text(" ", strip=True)
        href = urljoin(BASE_URL, link.get("href", ""))
        slug = href.rstrip("/").split("/")[-1]

        if not name or not slug:
            continue

        # TGJU quotes these prices in rials.
        rial_price = parse_number(cells[1].get_text(" ", strip=True))
        if rial_price <= 0:
            continue

        change = ""
        for cell in cells[1:]:
            text = cell.get_text(" ", strip=True)
            if "%" in text:
                match = re.search(
                    r"[-+]?\s*[\d۰-۹٠-٩,٬٫.]+\s*%", text
                )
                if match:
                    change = match.group(0).strip()
                    break

        items.append({
            "name": name,
            "slug": slug,
            "price": round(rial_price / 10),
            "change": change,
            "url": href,
        })

    return items


def unique_items(items):
    result = []
    seen = set()

    for item in items:
        if item["slug"] not in seen:
            seen.add(item["slug"])
            result.append(item)

    return result


def get_currency_items():
    # The currency board; includes the currencies actually listed there.
    items = parse_market_page(f"{BASE_URL}/currency")
    return unique_items(items)


def get_physical_gold_items():
    urls = [
        f"{BASE_URL}/gold-chart",
        f"{BASE_URL}/coin",
        f"{BASE_URL}/قیمت-سکه-پارسیان",
    ]

    items = []
    for url in urls:
        try:
            items.extend(parse_market_page(url))
        except Exception as exc:
            print(f"Warning: could not read {url}: {exc}")

    include_words = (
        "طلا", "آبشده", "مثقال", "سکه", "شمش",
        "geram", "gold", "sekke", "parsian", "melt",
        "abshodeh", "coin",
    )
    exclude_words = (
        "صندوق", "بورس", "گواهی", "آینده", "رفاه",
        "سامان", "نقره", "انس", "silver", "fund",
        "certificate", "future",
    )

    selected = []
    for item in items:
        searchable = (item["name"] + " " + item["slug"]).lower()

        if any(word in searchable for word in exclude_words):
            continue
        if any(word in searchable for word in include_words):
            selected.append(item)

    return unique_items(selected)


def build_messages(kind, items):
    if not items:
        raise RuntimeError(
            "هیچ قیمت معتبری پیدا نشد؛ برای جلوگیری از انتشار داده خالی، "
            "پیام ارسال نمی‌شود."
        )

    now = datetime.now(ZoneInfo("Asia/Tehran"))
    timestamp = fa(now.strftime("%Y/%m/%d - %H:%M"))

    if kind == "currency":
        title = "💱 <b>قیمت ارزها در بازار ایران</b>"
        items.sort(key=lambda x: x["name"])
    else:
        title = "🪙 <b>قیمت طلای فیزیکی و سکه در بازار ایران</b>"
        items.sort(key=lambda x: x["name"])

    lines = [
        title,
        f"🕒 زمان انتشار: {timestamp}",
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
        'منبع قیمت‌ها: <a href="https://www.tgju.org/">TGJU</a>',
        "<b>@FundBoard_Gold | فاندبورد طلا</b>",
        "<b>‎داشبورد سرمایه‌گذاری شما</b>",
    ])

    # Split long reports to respect Telegram's message limit.
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
        raise RuntimeError("تنظیمات توکن یا کانال تلگرام موجود نیست.")

    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"

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
            raise RuntimeError(f"Telegram API error: {result}")

        time.sleep(1)


def main():
    kind = os.environ.get("MARKET_KIND", "currency").lower()

    if kind == "currency":
        items = get_currency_items()
    elif kind == "gold":
        items = get_physical_gold_items()
    else:
        raise ValueError("MARKET_KIND باید currency یا gold باشد.")

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام استخراج‌شده: {len(items)}")

    messages = build_messages(kind, items)

    for index, message in enumerate(messages, start=1):
        print(f"\n--- پیام {index}/{len(messages)} ---\n")
        print(message)

    if os.environ.get("PUBLISH_TO_TELEGRAM", "false").lower() == "true":
        send_telegram(messages)
        print("انتشار در تلگرام با موفقیت انجام شد.")
    else:
        print("حالت آزمایشی: پیامی به تلگرام ارسال نشد.")


if __name__ == "__main__":
    main()
