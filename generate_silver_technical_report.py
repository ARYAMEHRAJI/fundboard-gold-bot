import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

CHANNEL = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver")
TOKEN = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
PUBLISH = os.getenv("PUBLISH_TO_TELEGRAM", "false").lower() == "true"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/SI=F?range=6mo&interval=1d"

def fa(value):
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def rsi(values, period=14):
    if len(values) <= period:
        return None
    changes = [values[i] - values[i-1] for i in range(1, len(values))]
    recent = changes[-period:]
    gains = sum(x for x in recent if x > 0) / period
    losses = -sum(x for x in recent if x < 0) / period
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))

def fetch_data():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        raise RuntimeError("داده تاریخی قرارداد آتی نقره از Yahoo Finance دریافت نشد.")
    node = result[0]
    quotes = node.get("indicators", {}).get("quote", [{}])[0]
    closes = [float(x) for x in quotes.get("close", []) if x is not None]
    highs = [float(x) for x in quotes.get("high", []) if x is not None]
    lows = [float(x) for x in quotes.get("low", []) if x is not None]
    timestamps = node.get("timestamp", [])
    if len(closes) < 55 or len(highs) < 10 or len(lows) < 10:
        raise RuntimeError("داده تاریخی کافی برای محاسبه شاخص‌های تکنیکال موجود نیست.")
    return node, closes, highs, lows, timestamps

def build_post():
    node, closes, highs, lows, timestamps = fetch_data()
    last = closes[-1]
    previous = closes[-2]
    change = (last / previous - 1) * 100
    ma20, ma50 = sma(closes, 20), sma(closes, 50)
    current_rsi = rsi(closes)
    support = min(lows[-20:])
    resistance = max(highs[-20:])
    if last > ma20 and ma20 > ma50:
        trend = "صعودی؛ قیمت بالاتر از میانگین‌های ۲۰ و ۵۰روزه است"
    elif last < ma20 and ma20 < ma50:
        trend = "نزولی؛ قیمت پایین‌تر از میانگین‌های ۲۰ و ۵۰روزه است"
    else:
        trend = "ترکیبی یا خنثی؛ هم‌جهتی روشنی بین قیمت و میانگین‌ها دیده نمی‌شود"
    if current_rsi >= 70:
        momentum = "RSI در محدوده بالای ۷۰ است؛ مومنتوم قوی و احتمال داغ‌شدن کوتاه‌مدت بازار"
    elif current_rsi <= 30:
        momentum = "RSI در محدوده زیر ۳۰ است؛ فشار فروش بالا بوده و احتمال برگشت باید جداگانه بررسی شود"
    else:
        momentum = "RSI در محدوده میانی قرار دارد"
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    date = now.strftime("%Y/%m/%d")
    time = now.strftime("%H:%M")
    lines = [
        "📊 <b>تحلیل تکنیکال نقره جهانی</b>",
        f"🕒 زمان گزارش: {fa(date)} - {fa(time)} به وقت تهران",
        "",
        f"• <b>آخرین قیمت تسویه روزانه:</b> {fa(f'{last:,.2f}')} دلار",
        f"• <b>تغییر نسبت به جلسه قبل:</b> {fa(f'{change:+.2f}')}٪",
        f"• <b>میانگین ۲۰روزه:</b> {fa(f'{ma20:,.2f}')} دلار",
        f"• <b>میانگین ۵۰روزه:</b> {fa(f'{ma50:,.2f}')} دلار",
        f"• <b>شاخص RSI-14:</b> {fa(f'{current_rsi:.1f}')}",
        "",
        f"🔎 <b>برداشت روند:</b> {trend}",
        f"📈 <b>مومنتوم:</b> {momentum}",
        f"• <b>محدوده حمایت مشاهده‌شده ۲۰ جلسه اخیر:</b> {fa(f'{support:,.2f}')} دلار",
        f"• <b>محدوده مقاومت مشاهده‌شده ۲۰ جلسه اخیر:</b> {fa(f'{resistance:,.2f}')} دلار",
        "",
        "این گزارش صرفاً خلاصه شاخص‌های تاریخی است؛ حمایت و مقاومت تقریبی‌اند و توصیه خریدوفروش محسوب نمی‌شوند.",
        "",
        '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره\n‎داشبورد</a></b> <b><a href="https://t.me/FundBoard_Silver">سرمایه‌گذاری شما</a></b>',
    ]
    return "\n".join(lines)

def main():
    post = build_post()
    print(post)
    if not PUBLISH:
        print("\nحالت آزمایشی: پیامی ارسال نشد.")
        return
    if not TOKEN:
        raise RuntimeError("Secret با نام TELEGRAM_SILVER_BOT_TOKEN تنظیم نشده است.")
    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHANNEL, "text": post, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram API ارسال پیام را تأیید نکرد.")
    print("تحلیل تکنیکال نقره با موفقیت ارسال شد.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        sys.exit(1)
