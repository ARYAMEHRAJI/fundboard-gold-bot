
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


def norm(s):
    s = str(s).translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    ))
    s = s.replace("\u200c", " ").replace("\u200e", "")
    s = s.replace("\u200f", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def num(s):
    s = norm(s).replace(",", "").replace("٬", "").replace("،", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def fa(s):
    return str(s).translate(str.maketrans(
        "0123456789", "۰۱۲۳۴۵۶۷۸۹"
    ))


def fmt(n):
    return f"{int(round(n)):,}"


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
    t = norm(text)
    names = list(allowed.keys()) + list(ALIASES.keys())
    for candidate in sorted(names, key=len, reverse=True):
        if norm(candidate) in t:
            canonical = ALIASES.get(candidate, candidate)
            if canonical in allowed:
                return canonical
    return None


def parse_row(row, allowed, url):
    cells = row.find_all("td", recursive=False)
    if len(cells) < 3:
        return None

    row_text = row.get_text(" ", strip=True)
    key = identify_name(row_text, allowed)
    if not key:
        return None

    texts = [c.get_text(" ", strip=True) for c in cells]

    # قیمت زنده در جدول TGJU در ستون دومِ قابل مشاهده است.
    # اگر عدد معتبر نباشد، ردیف را رد می‌کنیم و حدس نمی‌زنیم.
    price = num(texts[1])
    if price is None or price <= 0:
        return None

    # ستون سوم شامل درصد و مبلغ تغییر است.
    change_text = texts[2]
    change_norm = norm(change_text)

    pm = re.search(r"\(\s*([-+]?\d+(?:\.\d+)?)\s*%\s*\)", change_norm)
    percent = float(pm.group(1)) if pm else None

    remainder = change_norm
    if pm:
        remainder = (
            remainder[:pm.start()] + remainder[pm.end():]
        )

    change_amount = num(remainder)

    return {
        "key": key,
        "name": allowed[key],
        "price_rial": price,
        "change_percent": percent,
        "change_rial": change_amount,
        "source": url,
    }


def scrape_page(url, allowed, output):
    soup = fetch(url)
    found = 0

    # ابتدا جدول‌هایی که هدر قیمت زنده دارند بررسی می‌شوند.
    tables = soup.find_all("table")
    matched_table = False

    for table in tables:
        headers = [
            norm(th.get_text(" ", strip=True))
            for th in table.find_all("th")
        ]

        has_live_price = any(
            "قیمت زنده" in h or h == "rates"
            for h in headers
        )

        if not has_live_price:
            continue

        matched_table = True

        for row in table.find_all("tr"):
            record = parse_row(row, allowed, url)
            if not record:
                continue

            key = record["key"]
            old = output.get(key)

            # اگر نامی در چند جدول تکرار شده باشد، رکورد دارای
            # اطلاعات تغییر کامل‌تر نگه داشته می‌شود.
            if old is None or (
                old["change_percent"] is None
                and record["change_percent"] is not None
            ):
                output[key] = record
                found += 1

    print(f"صفحه دریافت شد: {url}")
    print(f"جدول دارای هدر قیمت زنده: {matched_table}")
    print(f"اقلام معتبر این صفحه: {found}")


def scrape(kind):
    if kind == "currency":
        allowed = CURRENCIES
        urls = [CURRENCY_URL]
    elif kind == "gold":
        allowed = GOLD
        urls = [GOLD_URL, COIN_URL]
    else:
        raise ValueError("MARKET_KIND باید currency یا gold باشد.")

    output = {}

    for url in urls:
        scrape_page(url, allowed, output)

    if not output:
        raise RuntimeError(
            "قیمت معتبر استخراج نشد؛ پیام منتشر نمی‌شود. "
            "ساختار جدول منبع با قالب مورد انتظار مطابقت ندارد."
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
        # نرخ‌های جدول TGJU به ریال هستند.
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

    messages, current = [], []

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
        raise RuntimeError("تلگرام ارسال پیام را تأیید نکرد.")


def main():
    kind = os.getenv("MARKET_KIND", "currency").strip().lower()
    publish = (
        os.getenv("PUBLISH_TO_TELEGRAM", "false").strip().lower()
        == "true"
    )

    items = scrape(kind)

    # جلوگیری از انتشار قیمت‌های غیرمنطقی یا صفر
    for item in items:
        if item["price_rial"] <= 0:
            raise RuntimeError(
                f"قیمت نامعتبر برای {item['name']}؛ انتشار لغو شد."
            )

    messages = build_messages(kind, items)

    print(f"نوع بازار: {kind}")
    print(f"تعداد اقلام: {len(items)}")
    print(f"تعداد پیام‌ها: {len(messages)}")

    for i, message in enumerate(messages, 1):
        print(f"\n--- پیام {i}/{len(messages)} ---")
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
