import os
import re
import sys
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.tgju.org"

URLS = {
    "currency": f"{BASE_URL}/currency",
    "gold": f"{BASE_URL}/gold-chart",
}

CURRENCY_ITEMS = {
    "دلار": "دلار آمریکا",
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

GOLD_ITEMS = {
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


def normalize_digits(text):
    """تبدیل ارقام فارسی و عربی به ارقام انگلیسی."""
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    return text.translate(table)


def normalize_name(text):
    """یکسان‌سازی جزئی نام‌ها برای تطبیق با فهرست مجاز."""
    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_number(text):
    """استخراج عدد از متن قیمت."""
    text = normalize_digits(text)
    text = text.replace(",", "").replace("٬", "").replace("،", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def format_number(value):
    """نمایش عدد به شکل خوانا و با جداکننده هزارگان."""
    number = int(round(value))
    return f"{number:,}"


def format_fa_digits(text):
    table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(text).translate(table)


def extract_percent(row_text):
    """استخراج درصد تغییر روزانه، در صورت وجود."""
    text = normalize_digits(row_text)
    match = re.search(r"\(\s*(-?\d+(?:\.\d+)?)\s*%\s*\)", text)
    if not match:
        return None
    return float(match.group(1))


def scrape_prices(kind):
    if kind not in URLS:
        raise ValueError(
            "MARKET_KIND باید currency یا gold باشد."
        )

    url = URLS[kind]
    allowed_items = CURRENCY_ITEMS if kind == "currency" else GOLD_ITEMS

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = {}

    # فقط ردیف‌هایی پذیرفته می‌شوند که نامشان در فهرست مجاز باشد.
    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"], recursive=False)

        if len(cells) < 2:
            continue

        raw_name = normalize_name(cells[0].get_text(" ", strip=True))
        raw_price = cells[1].get_text(" ", strip=True)

        if raw_name not in allowed_items:
            continue

        price_rial = to_number(raw_price)

        if price_rial is None or price_rial <= 0:
            continue

        # قیمت‌های این صفحات TGJU به ریال هستند.
        price_toman = price_rial / 10

        # تغییر درصد از متن کل ردیف خوانده می‌شود.
        percent = extract_percent(
            row.get_text(" ", strip=True)
        )

        # اولین قیمت معتبر هر نام نگه داشته می‌شود.
        if raw_name not in results:
            results[raw_name] = {
                "name": allowed_items[raw_name],
                "price": price_toman,
                "percent": percent,
            }

    if not results:
        raise RuntimeError(
            f"هیچ قیمت معتبری از {url} استخراج نشد. "
            "برای جلوگیری از انتشار داده اشتباه، پیام ارسال نمی‌شود."
        )

    print(f"صفحه دریافت شد: {url} (HTTP {response.status_code})")
    print(f"تعداد اقلام معتبر: {len(results)}")

    return list(results.values())


def build_messages(kind, items):
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date_text = format_fa_digits(now.strftime("%Y/%m/%d"))
    time_text = format_fa_digits(now.strftime("%H:%M"))

    if kind == "currency":
        title = "💱 <b>قیمت ارزها در بازار ایران</b>"
        source_label = "منبع: TGJU"
    else:
        title = "🪙 <b>قیمت طلای فیزیکی در بازار ایران</b>"
        source_label = "منبع: TGJU"

    lines = [
        title,
        f"🕒 زمان گزارش: {date_text} - {time_text}",
        "",
    ]

    for item in items:
        name = html.escape(item["name"])
        price = format_fa_digits(format_number(item["price"]))
        line = f"• {name}: <b>{price} تومان</b>"

        percent = item.get("percent")
        if percent is not None:
            percent_text = format_fa_digits(f"{percent:g}")
            sign = "+" if percent > 0 else ""
            sign = format_fa_digits(sign)
            line += f" ({sign}{percent_text}٪)"

        lines.append(line)

    lines.extend(["", html.escape(source_label)])

    # تلگرام برای هر پیام محدودیت طول دارد.
    # تقسیم‌بندی پیام‌ها با حفظ خطوط انجام می‌شود.
    messages = []
    current = []

    for line in lines:
        candidate = "\n".join(current + [line])

        if len(candidate) > 3500 and current:
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
        raise RuntimeError(
            "یکی از متغیرهای TELEGRAM_BOT_TOKEN یا "
            "TELEGRAM_CHANNEL_ID تنظیم نشده است."
        )

    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"

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

    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(
            "تلگرام ارسال پیام را تأیید نکرد."
        )


def main():
    kind = os.getenv("MARKET_KIND", "currency").strip().lower()
    publish = (
        os.getenv("PUBLISH_TO_TELEGRAM", "false").strip().lower()
        == "true"
    )

    items = scrape_prices(kind)
    messages = build_messages(kind, items)

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام استخراج‌شده: {len(items)}")
    print(f"تعداد پیام‌ها: {len(messages)}")

    for index, message in enumerate(messages, start=1):
        print(f"\n--- پیام {index}/{len(messages)} ---")
        print(message)

    if not publish:
        print("\nحالت آزمایشی: هیچ پیامی به تلگرام ارسال نشد.")
        return

    for message in messages:
        send_telegram(message)

    print("پیام‌ها با موفقیت به تلگرام ارسال شدند.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        sys.exit(1)
        
