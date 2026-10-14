import os
import re
import sys
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.tgju.org"
CURRENCY_URL = f"{BASE}/currency"
GOLD_URL = f"{BASE}/gold-chart"
COIN_URL = f"{BASE}/coin"

CURRENCIES = {
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

ALIASES = {
    "دلار": "دلار آمریکا",
    "طلای 18 عیار/750": "طلای 18 عیار / 750",
    "طلای 18 عیار/740": "طلای 18 عیار / 740",
    "طلای ۱۸ عیار / ۷۵۰": "طلای 18 عیار / 750",
    "طلای ۱۸ عیار/۷۵۰": "طلای 18 عیار / 750",
    "طلای ۲۴ عیار": "طلای 24 عیار",
    "نیم‌سکه": "نیم سکه",
    "ربع‌سکه": "ربع سکه",
}


def norm(value):
    value = str(value or "")
    value = value.translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    ))
    value = value.replace("\u200c", " ")
    value = value.replace("\u200e", "")
    value = value.replace("\u200f", "")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def num(value):
    value = norm(value)
    value = value.replace(",", "").replace("٬", "").replace("،", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def fa(value):
    return str(value).translate(
        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    )


def fmt(value):
    return f"{int(round(value)):,}"


def fetch(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
        timeout=30,
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def identify_name(text, allowed):
    cleaned = norm(text)
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)

    candidates = {norm(key): key for key in allowed}

    for alias, canonical in ALIASES.items():
        if canonical in allowed:
            candidates[norm(alias)] = canonical

    return candidates.get(cleaned)


def header_kind(text):
    text = norm(text)

    if not text:
        return None

    if any(w in text for w in (
        "تغییر", "درصد تغییر", "change", "نوسان"
    )):
        return "change"

    if any(w in text for w in (
        "کمترین", "پایین ترین", "low", "حداقل"
    )):
        return "low"

    if any(w in text for w in (
        "بیشترین", "بالاترین", "high", "حداکثر"
    )):
        return "high"

    if any(w in text for w in (
        "زمان", "تاریخ", "time", "date"
    )):
        return "time"

    if any(w in text for w in (
        "عنوان نرخ", "نام نرخ", "نام دارایی",
        "نماد", "عنوان"
    )):
        return "name"

    if any(w in text for w in (
        "قیمت زنده", "قیمت نقدی", "قیمت پایانی",
        "آخرین قیمت", "قیمت فعلی", "قیمت",
        "price", "rates"
    )):
        return "price"

    return None


def get_table_headers(table):
    best_headers = []
    best_score = 0

    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)

        if not cells:
            continue

        kinds = [
            header_kind(cell.get_text(" ", strip=True))
            for cell in cells
        ]
        score = sum(kind is not None for kind in kinds)

        if score > best_score:
            best_score = score
            best_headers = kinds

    return best_headers


def cell_kind(cell):
    labels = []

    for attr in ("data-title", "data-label", "aria-label", "title"):
        value = cell.get(attr)
        if value:
            labels.append(value)

    classes = cell.get("class", [])
    if isinstance(classes, str):
        classes = classes.split()

    labels.extend(classes)
    return header_kind(" ".join(labels))


def cell_number(cell):
    for attr in ("data-value", "data-price", "data-live-price"):
        value = cell.get(attr)

        if value:
            parsed = num(value)
            if parsed is not None and parsed > 0:
                return parsed

    return num(cell.get_text(" ", strip=True))


def find_cell_index(cells, headers, target):
    # اولویت با برچسب واقعی خود سلول است.
    for index, cell in enumerate(cells):
        if cell_kind(cell) == target:
            return index

    # اگر چند هدر قیمت وجود داشته باشد، اولین مورد را کورکورانه
    # انتخاب نمی‌کنیم؛ انتخاب قیمت در parse_row انجام می‌شود.
    for index, kind in enumerate(headers):
        if kind == target and index < len(cells):
            return index

    return None


def parse_change(text):
    text = norm(text)

    match = re.search(
        r"\(\s*([-+]?\d+(?:\.\d+)?)\s*%\s*\)",
        text
    )

    percent = float(match.group(1)) if match else None
    remainder = text

    if match:
        remainder = (
            remainder[:match.start()] + remainder[match.end():]
        )

    return percent, num(remainder)


def parse_row(row, allowed, url, headers):
    cells = row.find_all(["th", "td"], recursive=False)

    if not cells:
        return None

    # نام دارایی را با تطبیق دقیق پیدا می‌کنیم.
    name_index = None
    key = None

    for index, cell in enumerate(cells):
        candidate = identify_name(
            cell.get_text(" ", strip=True),
            allowed
        )

        if candidate is not None:
            name_index = index
            key = candidate
            break

    if name_index is None:
        return None

    # اصلاح اصلی:
    # قیمت باید در سلولی بعد از نام دارایی باشد.
    # هدرهای TGJU ممکن است دو بار "price" داشته باشند و
    # اندیس هدرها لزوماً با ساختار ردیف داده هم‌خوان نیست.
    price_index = None
    price = None

    # ابتدا سلول‌های بعد از نام را به ترتیب بررسی می‌کنیم.
    for index in range(name_index + 1, len(cells)):
        cell = cells[index]

        # اگر سلول برچسب تغییرات دارد، قیمت نیست.
        if cell_kind(cell) == "change":
            continue

        value = cell_number(cell)

        if value is not None and value > 0:
            price_index = index
            price = value
            break

    if price_index is None:
        print(
            f"قیمت معتبر پیدا نشد: {key} | "
            f"سلول‌ها: "
            f"{[c.get_text(' ', strip=True) for c in cells]}"
        )
        return None

    # تغییرات روزانه را با برچسب سلول یا هدر پیدا می‌کنیم.
    change_index = None

    for index, cell in enumerate(cells):
        if index == name_index or index == price_index:
            continue

        if cell_kind(cell) == "change":
            change_index = index
            break

    if change_index is None:
        for index, kind in enumerate(headers):
            if kind == "change" and index < len(cells):
                if index not in (name_index, price_index):
                    change_index = index
                    break

    change_text = ""

    if change_index is not None:
        change_text = cells[change_index].get_text(
            " ", strip=True
        )

    percent, amount = parse_change(change_text)

    print(
        f"DEBUG {key}: price_rial={price}, "
        f"price_index={price_index}, "
        f"change={change_text!r}"
    )

    return {
        "key": key,
        "name": allowed[key],
        "price_rial": price,
        "change_percent": percent,
        "change_rial": amount,
        "source": url,
    }


def scrape_page(url, allowed, output):
    soup = fetch(url)
    found = 0
    matched_table = False

    for table in soup.find_all("table"):
        headers = get_table_headers(table)

        if "price" not in headers:
            continue

        matched_table = True

        print(f"\nصفحه: {url}")
        print("هدرها:", headers)

        for row in table.find_all("tr"):
            record = parse_row(row, allowed, url, headers)

            if not record:
                continue

            key = record["key"]
            old = output.get(key)

            if old is None:
                output[key] = record
                found += 1
            elif (
                old["change_percent"] is None
                and record["change_percent"] is not None
            ):
                output[key] = record

    print(f"صفحه دریافت شد: {url}")
    print(f"جدول دارای هدر قیمت: {matched_table}")
    print(f"اقلام معتبر این صفحه: {found}")


def scrape(kind):
    if kind == "currency":
        allowed = CURRENCIES
        urls = [CURRENCY_URL]
        required = {"دلار آمریکا"}

    elif kind == "gold":
        allowed = GOLD
        urls = [GOLD_URL, COIN_URL]
        required = {
            "طلای 18 عیار / 750",
            "سکه امامی",
        }

    else:
        raise ValueError(
            "MARKET_KIND باید currency یا gold باشد."
        )

    output = {}

    for url in urls:
        scrape_page(url, allowed, output)

    missing = required - set(output.keys())

    if missing:
        raise RuntimeError(
            "قیمت اقلام ضروری استخراج نشد: "
            + "؛ ".join(sorted(missing))
            + "؛ انتشار لغو شد."
        )

    if not output:
        raise RuntimeError(
            "هیچ قیمت معتبری استخراج نشد؛ انتشار لغو شد."
        )

    return list(output.values())


def format_change(item):
    parts = []
    percent = item["change_percent"]
    amount = item["change_rial"]

    if percent is not None:
        sign = "+" if percent > 0 else ""
        parts.append(f"{sign}{fa(f'{percent:g}')}٪")

    if amount is not None:
        sign = "+" if amount > 0 else (
            "−" if amount < 0 else ""
        )

        parts.append(
            f"{fa(sign + fmt(abs(amount)))} ریال "
            f"(معادل "
            f"{fa(sign + fmt(abs(amount) / 10))} تومان)"
        )

    if not parts:
        return "   تغییر روزانه: اطلاعات موجود نیست"

    return "   تغییر روزانه: " + " | ".join(parts)


def build_messages(kind, items):
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date = fa(now.strftime("%Y/%m/%d"))
    time = fa(now.strftime("%H:%M"))

    if kind == "currency":
        title = "💱 <b>قیمت ارزها در بازار ایران</b>"
    else:
        title = "🪙 <b>قیمت طلا و انواع سکه در بازار ایران</b>"

    lines = [
        title,
        f"🕒 زمان گزارش: {date} - {time}",
        "",
    ]

    for item in items:
        price_toman = item["price_rial"] / 10

        lines.append(
            f"• {html.escape(item['name'])}: "
            f"<b>{fa(fmt(price_toman))} تومان</b>"
        )
        lines.append(format_change(item))

    lines.extend([
        "",
        'منبع: <a href="https://www.tgju.org/">TGJU</a>',
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
            "تنظیمات تلگرام در GitHub Secrets کامل نیست."
        )

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
        raise RuntimeError(
            "تلگرام ارسال پیام را تأیید نکرد."
        )


def main():
    kind = os.getenv(
        "MARKET_KIND", "currency"
    ).strip().lower()

    publish = os.getenv(
        "PUBLISH_TO_TELEGRAM", "false"
    ).strip().lower() == "true"

    items = scrape(kind)
    messages = build_messages(kind, items)

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام: {len(items)}")
    print(f"تعداد پیام‌ها: {len(messages)}")

    for index, message in enumerate(messages, 1):
        print(f"\n--- پیام {index}/{len(messages)} ---")
        print(message)

    if not publish:
        print("\nحالت آزمایشی: هیچ پیامی ارسال نشد.")
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
