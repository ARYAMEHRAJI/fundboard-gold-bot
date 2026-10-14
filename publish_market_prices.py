
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
    "currency": [
        f"{BASE_URL}/currency",
    ],
    "gold": [
        f"{BASE_URL}/gold-chart",
        f"{BASE_URL}/coin",
    ],
}

CURRENCY_ITEMS = {
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

ALIASES = {
    "طلای 18 عیار/750": "طلای 18 عیار / 750",
    "طلای 18 عیار / 750": "طلای 18 عیار / 750",
    "طلای 18 عیار/740": "طلای 18 عیار / 740",
    "طلای 18 عیار / 740": "طلای 18 عیار / 740",
    "طلای 24 عیار": "طلای 24 عیار",
    "طلای دست دوم": "طلای دست دوم",
    "مثقال طلا": "مثقال طلا",
    "آبشده نقدی": "آبشده نقدی",
    "آبشده معاملاتی": "آبشده معاملاتی",
    "سکه امامی": "سکه امامی",
    "سکه بهار آزادی": "سکه بهار آزادی",
    "نیم سکه": "نیم سکه",
    "ربع سکه": "ربع سکه",
    "سکه گرمی": "سکه گرمی",
    "ین ژاپن (100 ین)": "ین ژاپن (100 ین)",
}


def normalize_digits(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    return str(text).translate(table)


def normalize_name(text):
    text = normalize_digits(text)
    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_number(text):
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
    return f"{int(round(value)):,}"


def format_fa(text):
    return str(text).translate(
        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    )


def normalize_percent(value):
    return f"{value:g}"


def parse_change(change_text):
    """
    ساختار معمول ستون تغییر در TGJU:
    (2.21%) 56,950

    مبلغ تغییر از منبع به ریال خوانده می‌شود.
    """
    text = normalize_digits(change_text)
    text = text.replace(",", "").replace("٬", "")

    percent_match = re.search(
        r"\(\s*(-?\d+(?:\.\d+)?)\s*%\s*\)",
        text,
    )

    percent = (
        float(percent_match.group(1))
        if percent_match
        else None
    )

    amount_text = text
    if percent_match:
        amount_text = (
            amount_text[:percent_match.start()]
            + amount_text[percent_match.end():]
        )

    amount = to_number(amount_text)

    return percent, amount


def make_alias_lookup(allowed_items):
    lookup = {}

    for source_name, display_name in allowed_items.items():
        lookup[normalize_name(source_name)] = (
            source_name,
            display_name,
        )

    for alias, canonical in ALIASES.items():
        if canonical in allowed_items:
            lookup[normalize_name(alias)] = (
                canonical,
                allowed_items[canonical],
            )

    # بعضی نام‌ها با فاصله‌گذاری متفاوت در منبع ظاهر می‌شوند.
    return lookup


def scrape_page(url, allowed_items, results):
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
    lookup = make_alias_lookup(allowed_items)
    found_here = 0

    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)

        if len(cells) < 2:
            continue

        raw_name = normalize_name(
            cells[0].get_text(" ", strip=True)
        )

        match = lookup.get(raw_name)

        if not match:
            # تطبیق محافظه‌کارانه؛ نام‌های ناشناخته را حدس نمی‌زنیم.
            continue

        canonical_name, display_name = match

        raw_price = cells[1].get_text(" ", strip=True)
        price_rial = to_number(raw_price)

        if price_rial is None or price_rial <= 0:
            continue

        percent = None
        change_rial = None

        if len(cells) >= 3:
            change_text = cells[2].get_text(" ", strip=True)
            percent, change_rial = parse_change(change_text)

        # مقدار صفحه TGJU به ریال است؛ قیمت اصلی به تومان تبدیل می‌شود.
        record = {
            "key": canonical_name,
            "name": display_name,
            "price_rial": price_rial,
            "price_toman": price_rial / 10,
            "change_percent": percent,
            "change_rial": change_rial,
            "source": url,
        }

        # در صورت تکرار، فقط رکورد دارای اطلاعات تغییر کامل‌تر جایگزین شود.
        previous = results.get(canonical_name)

        if previous is None:
            results[canonical_name] = record
            found_here += 1
        elif (
            previous.get("change_rial") is None
            and record.get("change_rial") is not None
        ):
            results[canonical_name] = record

    print(f"صفحه دریافت شد: {url} (HTTP {response.status_code})")
    print(f"اقلام معتبر در این صفحه: {found_here}")


def scrape_prices(kind):
    if kind not in URLS:
        raise ValueError("MARKET_KIND باید currency یا gold باشد.")

    allowed_items = (
        CURRENCY_ITEMS if kind == "currency" else GOLD_ITEMS
    )

    results = {}

    for url in URLS[kind]:
        scrape_page(url, allowed_items, results)

    if not results:
        raise RuntimeError(
            "هیچ قیمت معتبری استخراج نشد؛ پیام منتشر نمی‌شود."
        )

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام یکتا: {len(results)}")

    return list(results.values())


def change_line(item):
    percent = item.get("change_percent")
    amount_rial = item.get("change_rial")

    if percent is None and amount_rial is None:
        return "   تغییر روزانه: اطلاعات در منبع موجود نیست"

    parts = []

    if percent is not None:
        percent_text = format_fa(normalize_percent(percent))
        if percent > 0:
            percent_text = "+" + percent_text
        parts.append(f"{percent_text}٪")

    if amount_rial is not None:
        sign = "+" if amount_rial > 0 else ""
        amount_toman = amount_rial / 10

        rial_text = format_fa(
            f"{sign}{format_number(abs(amount_rial))}"
        )
        toman_text = format_fa(
            f"{sign}{format_number(abs(amount_toman))}"
        )

        if amount_rial < 0:
            rial_text = "−" + format_fa(format_number(abs(amount_rial)))
            toman_text = "−" + format_fa(format_number(abs(amount_toman)))

        parts.append(
            f"تغییر مبلغ: {rial_text} ریال "
            f"(معادل {toman_text} تومان)"
        )

    return "   تغییر روزانه: " + " | ".join(parts)


def build_messages(kind, items):
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date_text = format_fa(now.strftime("%Y/%m/%d"))
    time_text = format_fa(now.strftime("%H:%M"))

    if kind == "currency":
        title = "💱 <b>قیمت ارزها در بازار ایران</b>"
    else:
        title = "🪙 <b>قیمت طلا و سکه در بازار ایران</b>"

    lines = [
        title,
        f"🕒 زمان تهیه گزارش: {date_text} - {time_text}",
        "",
    ]

    # ترتیب نمایش اقلام
    preferred_order = (
        list(CURRENCY_ITEMS.keys())
        if kind == "currency"
        else list(GOLD_ITEMS.keys())
    )

    by_key = {item["key"]: item for item in items}
    ordered = []

    for key in preferred_order:
        if key in by_key and by_key[key] not in ordered:
            ordered.append(by_key[key])

    # هر قلم فقط یک بار نمایش داده می‌شود.
    seen = set()

    for item in ordered:
        if item["key"] in seen:
            continue
        seen.add(item["key"])

        name = html.escape(item["name"])
        price = format_fa(format_number(item["price_toman"]))

        lines.append(f"• {name}: <b>{price} تومان</b>")
        lines.append(change_line(item))

    lines.extend([
        "",
        'منبع قیمت‌ها: <a href="https://www.tgju.org/">TGJU</a>',
    ])

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
            "TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL_ID تنظیم نشده است."
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
        raise RuntimeError("تلگرام ارسال پیام را تأیید نکرد.")


def main():
    kind = os.getenv("MARKET_KIND", "currency").strip().lower()

    publish = (
        os.getenv("PUBLISH_TO_TELEGRAM", "false").strip().lower()
        == "true"
    )

    items = scrape_prices(kind)

    # در گزارش طلا، وجود حداقل چند گروه اصلی بررسی می‌شود.
    if kind == "gold":
        required_groups = [
            {"طلای 18 عیار / 750", "طلای 24 عیار", "مثقال طلا"},
            {"سکه امامی", "سکه بهار آزادی", "نیم سکه", "ربع سکه", "سکه گرمی"},
        ]

        available = {item["key"] for item in items}

        for group in required_groups:
            if not available.intersection(group):
                raise RuntimeError(
                    "بخشی از اطلاعات اصلی طلا یا سکه استخراج نشده؛ "
                    "برای جلوگیری از انتشار گزارش ناقص، پیام ارسال نمی‌شود."
                )

    messages = build_messages(kind, items)

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

    print("ارسال پیام‌ها به تلگرام انجام شد.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        sys.exit(1)
