"""Publish one genuine, current silver-market update to the channel."""
import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

def main():
    token = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_SILVER_BOT_TOKEN secret")

    import publish_silver_prices
    items = [publish_silver_prices.parse_page(*p) for p in publish_silver_prices.PAGES]
    base = publish_silver_prices.build_post(items)

    # Remove the old duplicated footer and append one clean, HTML-safe footer.
    footer = '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره'
    if footer in base:
        base = base[:base.index(footer)].rstrip()

    nl = chr(10)
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    stamp = publish_silver_prices.fa(publish_silver_prices.jalali_date(now)) + " - " + publish_silver_prices.fa(now.strftime("%H:%M"))
    analysis = (
        "📌 <b>برداشت تحلیلی</b>" + nl
        + "قیمت نقره را باید هم‌زمان از دو مسیر بررسی کرد: قیمت جهانی هر اونس و نرخ ارز داخلی. "
        + "در بازار ایران، تغییر نرخ ارز می‌تواند اثر حرکت جهانی نقره را تقویت یا خنثی کند؛ "
        + "بنابراین مقایسه قیمت ریالی با اونس به‌تنهایی بدون توجه به نرخ دلار تصویر کاملی نمی‌دهد."
        + nl + nl + "این گزارش اطلاعات بازار است، نه سیگنال قطعی خرید یا فروش."
        + nl + "🕒 زمان تهیه تحلیل: " + stamp + " به وقت تهران"
    )
    message = base + nl + nl + analysis + nl + nl + '<a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره</a>'

    if len(message) > 4000:
        raise RuntimeError(f"Message too long for Telegram: {len(message)} characters")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": channel, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram rejected message: {data}")
    print(f"REAL_POST_SENT channel={channel} message_id={data['result']['message_id']}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
