"""Dry-run relative-performance report for silver versus gold futures. No Telegram publishing."""
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")
URLS = {
    "silver": "https://query1.finance.yahoo.com/v8/finance/chart/SI=F?range=6mo&interval=1d",
    "gold": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=6mo&interval=1d",
}

def fa(v):
    return str(v).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

def history(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 FundBoard/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        node = json.loads(response.read().decode())["chart"]["result"][0]
    closes = [float(x) for x in node["indicators"]["quote"][0]["close"] if x is not None]
    if len(closes) < 65:
        raise RuntimeError("کمتر از ۶۵ جلسه داده معتبر دریافت شد")
    return closes

def pct(values, sessions):
    return (values[-1] / values[-sessions-1] - 1) * 100

def main():
    silver, gold = history(URLS["silver"]), history(URLS["gold"])
    ratio = gold[-1] / silver[-1]
    now = datetime.now(TEHRAN)
    lines = [
        "⚖️ <b>مقایسه عملکرد طلا و نقره</b>",
        f"🕒 زمان گزارش: {fa(now.strftime('%Y/%m/%d - %H:%M'))} به وقت تهران",
        "",
        f"• قرارداد آتی نقره: <b>{fa(f'{silver[-1]:,.2f}')} دلار</b>",
        f"• قرارداد آتی طلا: <b>{fa(f'{gold[-1]:,.2f}')} دلار</b>",
        f"• نسبت قیمت طلا به نقره: <b>{fa(f'{ratio:.2f}')}</b>",
        "",
        f"• بازده حدود یک‌ماهه نقره: {fa(f'{pct(silver,21):+.2f}')}٪ | طلا: {fa(f'{pct(gold,21):+.2f}')}٪",
        f"• بازده حدود سه‌ماهه نقره: {fa(f'{pct(silver,63):+.2f}')}٪ | طلا: {fa(f'{pct(gold,63):+.2f}')}٪",
        "",
        "محاسبات بر پایه جلسات معاملاتی قراردادهای آتی هستند و بازده نقره فیزیکی یا صندوق‌های ایرانی را نشان نمی‌دهند.",
        "نسبت طلا به نقره به‌تنهایی سیگنال خریدوفروش نیست.",
        "",
        '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره\n‎داشبورد</a></b> <b><a href="https://t.me/FundBoard_Silver">سرمایه‌گذاری شما</a></b>',
    ]
    report = "\n".join(lines)
    print("MODE: DRY_RUN; TELEGRAM_MESSAGES_SENT=0")
    print(report)
    with open("silver_gold_comparison_preview.html","w",encoding="utf-8") as f:
        f.write(report+"\n")

if __name__ == "__main__":
    main()
