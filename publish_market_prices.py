
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

ALIASES = {
    "طلای 18 عیار/750": "طلای 18 عیار / 750",
    "طلای 18 عیار/740": "طلای 18 عیار / 740",
    "نیم‌سکه": "نیم سکه",
    "ربع‌سکه": "ربع سکه",
}


DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def norm(value):
    value = str(value).translate(DIGITS)
    value = value.replace("\u200c", " ")
    value = value.replace("\u200e", "").replace("\u200f", "")
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip().lower()


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
    return str(value).translate(str.maketrans(
        "0123456789", "۰۱۲۳۴۵۶۷۸۹"
    ))


def fmt(value):
    return f"{int(round(value)):,}"


def fetch(url):
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


def identify_name(text, allowed):
    text = norm(text)
    candidates = list(allowed.keys()) + list(ALIASES.keys())

    for candidate in sorted(candidates, key=len, reverse=True):
        if norm(candidate) in text:
            canonical = ALIASES.get(candidate, candidate)
            if canonical in allowed:
                return canonical

    return None


def header_kind(text):
    """تبدیل عنوان هدر جدول به نوع داده."""
    value = norm(text)

    if "قیمت زنده" in value or value == "rates":
        return "price"

    if value == "تغییر" or value.startswith("تغییر "):
        return "change"

    if "عنوان نرخ" in value or value in ("عنوان", "نام"):
        return "name"

    return None


def cell_header(cell):
    """عنوان احتمالی یک سلول از ویژگی‌های HTML."""
    for attr in ("data-title", "data-label", "aria-label"):
        value = cell.get(attr)
        if value and header_kind(value):
            return header_kind(value)

    return None


def row_direction(row, change_cell):
    """
    تشخیص جهت تغییر از کلاس‌های HTML.
    اگر نشانه روشنی وجود نداشته باشد، None برمی‌گرداند.
    """
    elements = [row, change_cell] + change_cell.find_all(True)

    for element in elements:
        classes = " ".join(element.get("class", [])).lower()
        classes = classes.replace("_", "-")

        if any(word in classes for word in (
            "low", "down", "negative", "text-danger", "red"
        )):
            return -1

        if any(word in classes for word in (
            "high", "up", "positive", "text-success", "green"
        )):
            return 1

    return None


def extract_change(cell, row):
    text = norm(cell.get_text(" ", strip=True))

    percent_match = re.search(
        r"\(\s*([-+]?\d+(?:\.\d+)?)\s*%\s*\)", text
    )
    percent = float(percent_match.group(1)) if percent_match else None

    # مبلغ تغییر را جداگانه استخراج می‌کنیم؛ درصد را وارد مبلغ نمی‌کنیم.
    remainder = text
    if percent_match:
        remainder = (
            remainder[:percent_match.start()]
            + remainder[percent_match.end():]
        )

    amount = num(remainder)
    direction = row_direction(row, cell)

    # TGJU گاهی مبلغ تغییر را بدون علامت چاپ می‌کند.
    # جهت را فقط وقتی مشخص می‌کنیم که HTML نشانه معتبری داشته باشد.
    if amount is not None and amount > 0 and direction == -1:
        amount = -amount

    if amount == 0:
        amount = 0.0

    return percent, amount


def parse_row(row, allowed, headers, url):
    cells = row.find_all("td", recursive=False)
    if not cells:
        return None

    # نام را از سلولی پیدا می‌کنیم که واقعاً نام دارایی را دارد.
    key = None
    name_index = None

    for index, cell in enumerate(cells):
        cell_text = cell.get_text(" ", strip=True)
        found_key = identify_name(cell_text, allowed)

        if found_key:
            key = found_key
            name_index = index
            break

    if key is None:
        return None

    # اولویت اول: ویژگی‌های خود سلول، در صورت وجود.
    price_cell = None
    change_cell = None

    for cell in cells:
        kind = cell_header(cell)

        if kind == "price" and price_cell is None:
            price_cell = cell
        elif kind == "change" and change_cell is None:
            change_cell = cell

    # اولویت دوم: تطبیق هدرها با سلول نام و سلول‌های بعد از آن.
    # این روش از فرض نادرست «سلول دوم قیمت است» جلوگیری می‌کند.
    if headers and name_index is not None:
        name_header_index = None

        for i, header in enumerate(headers):
            if header_kind(header) == "name":
                name_header_index = i
                break

        if name_header_index is None:
            # در بعضی جدول‌ها نام در اولین ستون داده قرار دارد،
            # حتی اگر هدر نام به شکل متفاوتی نمایش داده شود.
            name_header_index = 0

        for header_index, header in enumerate(headers):
            kind = header_kind(header)
            cell_index = name_index + (header_index - name_header_index)

            if not (0 <= cell_index < len(cells)):
                continue

            if kind == "price" and price_cell is None:
                price_cell = cells[cell_index]
            elif kind == "change" and change_cell is None:
                change_cell = cells[cell_index]

    if price_cell is None:
        return None

    price_text = price_cell.get_text(" ", strip=True)
    price = num(price_text)

    if price is None or price <= 0:
        return None

    percent = None
    amount = None

    if change_cell is not None:
        percent, amount = extract_change(change_cell, row)

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
        header_row = table.find("tr")
        if header_row is None:
            continue

        headers = [
            cell.get_text(" ", strip=True)
            for cell in header_row.find_all(["th", "td"], recursive=False)
        ]

        if not any(header_kind(h) == "price" for h in headers):
            continue

        matched_table = True

        for row in table.find_all("tr"):
            record = parse_row(row, allowed, headers, url)
            if record is None:
                continue

            key = record["key"]
            old = output.get(key)

            # رکورد دارای تغییر روزانه کامل‌تر را ترجیح می‌دهیم.
            record_score = (
                record["change_percent"] is not None
            ) + (
                record["change_rial"] is not None
            )
            old_score = -1 if old is None else (
                old["change_percent"] is not None
            ) + (
                old["change_rial"] is not None
            )

            if old is None or record_score > old_score:
                output[key] = record
                found += 1

    print(f"صفحه دریافت شد: {url}")
    print(f"جدول دارای هدر قیمت زنده: {matched_table}")
    print(f"اقلام معتبر این صفحه: {found}")


def scrape(kind):
    if kind == "currency":
        allowed = CURRENCIES
        urls = [CURRENCY_URL]
        required = {"دلار"}
    elif kind == "gold":
        allowed = GOLD
        urls = [GOLD_URL, COIN_URL]
        required = {"طلای 18 عیار / 750", "سکه امامی"}
    else:
        raise ValueError("MARKET_KIND باید currency یا gold باشد.")

    output = {}

    for url in urls:
        scrape_page(url, allowed, output)

    missing = required - set(output.keys())
    if missing:
        raise RuntimeError(
            "قیمت اقلام ضروری استخراج نشد: "
            + ", ".join(sorted(missing))
            + "؛ انتشار لغو شد."
        )

    if not output:
        raise RuntimeError("هیچ قیمت معتبری استخراج نشد؛ انتشار لغو شد.")

    # چاپ تشخیصی برای بررسی قیمت‌ها در اجرای آزمایشی
    for item in output.values():
        print(
            "بررسی قیمت | "
            f"{item['name']} | "
            f"{fmt(item['price_rial'])} ریال | "
            f"تغییر: {item['change_rial']}"
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
        if amount < 0:
            rial = "−" + fmt(abs(amount))
            toman = "−" + fmt(abs(amount) / 10)
        else:
            sign = "+" if amount > 0 else ""
            rial = sign + fmt(amount)
            toman = sign + fmt(amount / 10)

        parts.append(
            f"{fa(rial)} ریال (معادل {fa(toman)} تومان)"
        )

    if not parts:
        return "   تغییر روزانه: اطلاعات موجود نیست"

    return "   تغییر روزانه: " + " | ".join(parts)


def build_messages(kind, items):
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date = fa(now.strftime("%Y/%m/%d"))
    time = fa(now.strftime("%H:%M"))

    title = (
        "💱 <b>قیمت ارزها در بازار ایران</b>"
        if kind == "currency"
        else "🪙 <b>قیمت طلا و انواع سکه در بازار ایران</b>"
    )

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

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"تلگرام ارسال را تأیید نکرد: {result}")


def main():
    kind = os.getenv("MARKET_KIND", "currency").strip().lower()
    publish = (
        os.getenv("PUBLISH_TO_TELEGRAM", "false").strip().lower()
        == "true"
    )

    items = scrape(kind)

    # حفاظت نهایی در برابر قیمت صفر یا نامعتبر
    for item in items:
        if item["price_rial"] <= 0:
            raise RuntimeError(
                f"قیمت نامعتبر برای {item['name']}؛ انتشار لغو شد."
            )

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
