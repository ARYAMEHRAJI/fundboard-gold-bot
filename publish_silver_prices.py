import os
import re
import sys
import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

PAGES = [
    ("انس جهانی نقره", "https://www.tgju.org/profile/silver", "USD/oz", "global"),
    ("گرم نقره ۹۹۹", "https://www.tgju.org/profile/silver_999", "ریال/گرم", "local"),
    ("گرم نقره ۹۲۵", "https://www.tgju.org/profile/silver_925", "ریال/گرم", "local"),
    ("دلار آزاد", "https://www.tgju.org/profile/price_dollar_rl", "ریال", "currency"),
]

def normalize_digits(text):
    return str(text).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

def fa(text):
    return str(text).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

def jalali_date(dt):
    # Gregorian-to-Jalali conversion
    g_days = [31,28,31,30,31,30,31,31,30,31,30,31]
    j_days = [31,31,31,31,31,31,30,30,30,30,30,29]
    gy, gm, gd = dt.year, dt.month, dt.day
    gy2, gm2, gd2 = gy-1600, gm-1, gd-1
    day_no = 365*gy2 + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400
    for i in range(gm2):
        day_no += g_days[i]
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        day_no += 1
    day_no += gd2
    day_no -= 79
    j_np = day_no // 12053
    day_no %= 12053
    jy = 979 + 33*j_np + 4*(day_no//1461)
    day_no %= 1461
    if day_no >= 366:
        jy += (day_no-1)//365
        day_no = (day_no-1)%365
    jm = 1
    for days in j_days:
        if day_no < days:
            break
        day_no -= days
        jm += 1
    return f"{jy:04d}/{jm:02d}/{day_no+1:02d}"

def parse_page(name, url, unit, kind):
    response = requests.get(url, headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36", "Accept-Language":"fa-IR,fa;q=0.9,en;q=0.8"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = normalize_digits(soup.get_text(" ", strip=True))
    price = None
    percent = None

    # Prefer the main "current rate" field on TGJU instrument pages.
    patterns = [
        r"نرخ\s*فعلی\s*[:：]?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
        r"(?:Last|Rate)\s*[:：]?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            price = float(match.group(1).replace(",", ""))
            break
    if price is None or price <= 0:
        raise RuntimeError(f"قیمت معتبر برای {name} از منبع دریافت نشد؛ انتشار متوقف شد.")

    # Read the daily percentage change when the page provides it.
    change_patterns = [
        r"درصد\s*تغییر\s*نسبت\s*به\s*روز\s*گذشته\s*[:：]?\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*%",
        r"درصد\s*تغییر\s*نسبت\s*به\s*نرخ\s*روز\s*گذشته\s*[:：]?\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*%",
        r"Change\s*%\s*[:：]?\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*%",
    ]
    for pattern in change_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            percent = float(match.group(1))
            break
    return {"name": name, "price": price, "unit": unit, "percent": percent, "kind": kind, "url": url}

def build_post(items):
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date = fa(jalali_date(now))
    time = fa(now.strftime("%H:%M"))
    lines = [
        "🥈 <b>قیمت نقره در بازار جهانی و ایران</b>",
        f"🕒 زمان گزارش: {date} - {time}",
        "",
    ]
    for item in items:
        if item["kind"] == "global":
            value = f'{item["price"]:,.3f} دلار'
        else:
            value = f'{item["price"]:,.0f} ریال'
        lines.append(f'• <b>{html.escape(item["name"])}</b>: <b>{fa(value)}</b>')
        if item["percent"] is None:
            lines.append("   تغییر روزانه: در منبع قابل تأیید نبود")
        else:
            sign = "+" if item["percent"] > 0 else ""
            lines.append(f'   تغییر روزانه: {fa(sign + format(item["percent"], ".2f"))}٪')
    lines.extend([
        "",
        '<a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره</a>',
    ])
    return "\n".join(lines)

def send(message):
    token = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver").strip()
    if not token:
        raise RuntimeError("Secret با نام TELEGRAM_SILVER_BOT_TOKEN تنظیم نشده است.")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": channel, "text": message, "parse_mode":"HTML", "disable_web_page_preview":True},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API خطا داد: {data}")
    print("پیام با موفقیت به تلگرام ارسال شد.")

def main():
    publish = os.getenv("PUBLISH_TO_TELEGRAM", "false").lower() == "true"
    items = [parse_page(*page) for page in PAGES]
    post = build_post(items)
    preview = Path("silver_content_preview/silver_prices.html")
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text(post + "\n", encoding="utf-8")
    print(f"PRICE_PREVIEW_FILE: {preview}")
    print(post)
    if publish:
        send(post)
    else:
        print("\nحالت آزمایشی: پیامی ارسال نشد.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        sys.exit(1)
