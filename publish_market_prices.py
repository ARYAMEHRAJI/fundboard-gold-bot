
import os
import re
import sys
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.tgju.org"

CURRENCY_URL = f"{BASE_URL}/currency"
GOLD_URL = f"{BASE_URL}/gold-chart"
COIN_URL = f"{BASE_URL}/coin"

CURRENCIES = {
    "دلار": "دلار آمریکا",
    "دلار آمریکا": "دلار آمریکا",
    "یورو": "یورو",
    "درهم امارات": "درهم امارات",
    "پوند انگلیس": "پوند انگلیس",
    "لیر ترکیه": "لیر ترکیه",
    "فرانک سوئیس": "فرانک سوئیس",
    "یوان چین": "یوان چین",
    "ین ژاپن (100 ین)": "ین ژاپن (۱۰۰ ین)",
    "وون کره جنوبی": "وون کره جنوبی",
    "دلار کانادا": "دلار کانادا",
    "دلار استرالیا": "دلار استرالیا",
    "دلار نیوزیلند": "دلار نیوزیلند",
    "دلار سنگاپور": "دلار سنگاپور",
    "روپیه هند": "روپیه هند",
    "روپیه پاکستان": "روپیه پاکستان",
    "دینار عراق": "دینار عراق",
    "افغانی": "افغانی افغانستان",
    "کرون دانمارک": "کرون دانمارک",
    "لاری گرجستان": "لاری گرجستان",
    "روبل روسیه": "روبل روسیه",
    "ریال عربستان": "ریال عربستان",
    "دینار کویت": "دینار کویت",
    "ریال قطر": "ریال قطر",
    "ریال عمان": "ریال عمان",
    "منات آذربایجان": "منات آذربایجان",
}

GOLD = {
    "طلای 18 عیار / 750": "طلای ۱۸ عیار",
    "طلای 18 عیار / 740": "طلای ۱۸ عیار / ۷۴۰",
    "طلای 24 عیار": "طلای ۲۴ عیار",
    "طلای دست دوم": "طلای دست دوم",
    "مثقال طلا": "مثقال طلا",
    "آبشده نقدی": "طلای آب‌شده نقدی",
    "آبشده معاملاتی": "طلای آب‌شده معاملاتی",
    "سکه امامی": "سکه امامی",
    "سکه بهار آزادی": "سکه بهار آزادی",
    "نیم سکه": "نیم‌سکه",
    "ربع سکه": "ربع‌سکه",
    "سکه گرمی": "سکه گرمی",
}


def normalize(text):
    text = str(text).translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    ))
    text = text.replace("\u200c", " ")
    text = text.replace("\u200e", "").replace("\u200f", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def number(text):
    text = normalize(text)
    text = text.replace(",", "").replace("٬", "").replace("،", "")
    match = re.search(r"(?<![a-zA-Z])[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def fa(text):
    return str(text).translate(str.maketrans(
        "0123456789", "۰۱۲۳۴۵۶۷۸۹"
    ))


def fmt(value):
    return f"{int(round(value)):,}"


def find_name(row_text, allowed):
    normalized_row = normalize(row_text)

    # نام‌های طولانی‌تر ابتدا بررسی می‌شوند تا تطبیق دقیق‌تر باشد.
    for source_name in sorted(allowed, key=len, reverse=True):
        if normalize(source_name) in normalized_row:
            return source_name

    return None


def parse_change(text):
    """
    تلاش برای استخراج درصد و مبلغ تغییر از متن ستون تغییر.
    اگر هر کدام در متن نباشد، مقدار آن None باقی می‌ماند.
    """
    text = normalize(text)

    percent_match = re.search(
        r"\(\s*([-+]?\d+(?:\.\d+)?)\s*%\s*\)", text
    )
    percent = float(percent_match.group(1)) if percent_match else None

    remainder = text
    if percent_match:
        remainder = (
            remainder[:percent_match.start()]
            + remainder[percent_match.end():]
        )

    amount = number(remainder)
    return percent, amount


def fetch_page(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
            ),
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
        timeout=30,
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def scrape_one_page(url, allowed, results):
    soup = fetch_page(url)
    found = 0

    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue

        row_text = row.get_text(" ", strip=True)
        source_name = find_name(row_text, allowed)

        if source_name is None:
            continue

        # در جدول‌های معمول TGJU، ستون دوم قیمت جاری است.
        price = number(cells[1].get_text(" ", strip=True))
        if price is None or price <= 0:
            continue

        change_percent = None
        change_amount_rial = None

        # ابتدا ستون تغییر احتمالی بررسی می‌شود.
        if len(cells) >= 3:
            change_text = " ".join(
                cell.get_text(" ", strip=True) for cell in cells[2:]
            )
            change_percent, change_amount_rial = parse_change(change_text)

        # اگر درصد در سلول‌ها نبود، متن کل ردیف هم بررسی می‌شود.
        if change_percent is None:
            row_percent, row_amount = parse_change(row_text)
            change_percent = row_percent
            if change_amount_rial is None:
                change_amount_rial = row_amount

        record = {
            "key": source_name,
            "name": allowed[source_name],
            "price_rial": price,
            "price_toman": price / 10,
            "change_percent": change_percent,
            "change_rial": change_amount_rial,
            "source": url,
        }

        old = results.get(source_name)

        if old is None:
            results[source_name] = record
            found += 1
        elif (
            old["change_percent"] is None
            and record["change_percent"] is not None
        ):
            results[source_name] = record

    print(f"صفحه دریافت شد: {url}")
    print(f"اقلام قابل شناسایی: {found}")


def scrape_prices(kind):
    results = {}

    if kind == "currency":
        scrape_one_page(CURRENCY_URL, CURRENCIES, results)
    elif kind == "gold":
        scrape_one_page(GOLD_URL, GOLD, results)
        scrape_one_page(COIN_URL, GOLD, results)
    else:
        raise ValueError("MARKET_KIND باید currency یا gold باشد.")

    if not results:
        raise RuntimeError(
            "قیمت معتبری استخراج نشد؛ انتشار لغو شد. "
            "ساختار جدول منبع احتمالاً تغییر کرده است."
        )

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام استخراج‌شده: {len(results)}")
    return list(results.values())


def change_description(item):
    percent = item["change_percent"]
    amount_rial = item["change_rial"]
    parts = []

    if percent is not None:
        sign = "+" if percent > 0 else ""
        parts.append(f"{sign}{fa(f'{percent:g}')}٪")

    if amount_rial is not None:
        sign = "+" if amount_rial > 0 else ""
        if amount_rial < 0:
            rial = "−" + fmt(abs(amount_rial))
            toman = "−" + fmt(abs(amount_rial) / 10)
        else:
            rial = sign + fmt(amount_rial)
            toman = sign + fmt(amount_rial / 10)

        parts.append(
            f"{fa(rial)} ریال (معادل {fa(toman)} تومان)"
        )

    if not parts:
        return "   تغییر روزانه: در منبع قابل استخراج نبود"

    return "   تغییر روزانه: " + " | ".join(parts)


def build_messages(kind, items):
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date_text = fa(now.strftime("%Y/%m/%d"))
    time_text = fa(now.strftime("%H:%M"))

    if kind == "currency":
        title = "💱 <b>قیمت ارزها در بازار ایران</b>"
    else:
        title = "🪙 <b>قیمت طلا و انواع سکه در بازار ایران</b>"

    lines = [
        title,
        f"🕒 زمان گزارش: {date_text} - {time_text}",
        "",
    ]

    for item in items:
        name = html.escape(item["name"])
        price = fa(fmt(item["price_toman"]))
        lines.append(f"• {name}: <b>{price} تومان</b>")
        lines.append(change_description(item))

    lines.extend([
        "",
        'منبع: <a href="https://www.tgju.org/">TGJU</a>',
    ])

    messages = []
    current = []

    for line in lines:
        if len("\n".join(current + [line])) > 3500 and current:
            messages.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        messages.append("\n".join(current))

    return messages


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()

    if not token or not chat_id:
        raise RuntimeError("تنظیمات تلگرام در GitHub Secrets کامل نیست.")

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()

    if not response.json().get("ok"):
        raise RuntimeError("ارسال پیام توسط تلگرام تأیید نشد.")


def main():
    kind = os.getenv("MARKET_KIND", "currency").strip().lower()
    publish = (
        os.getenv("PUBLISH_TO_TELEGRAM", "false").strip().lower()
        == "true"
    )

    items = scrape_prices(kind)
    messages = build_messages(kind, items)

    print(f"تعداد پیام‌ها: {len(messages)}")
    for i, message in enumerate(messages, 1):
        print(f"\n--- پیام {i}/{len(messages)} ---")
        print(message)

    if not publish:
        print("\nحالت آزمایشی: پیام ارسال نشد.")
        return

    for message in messages:
        send_telegram(message)

    print("ارسال پیام‌ها با موفقیت انجام شد.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        sys.exit(1)
