"""Periodic silver-market performance report. Price returns are explicitly not total returns. Dry-run only."""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")
OUT = Path("silver_content_preview/periodic_returns.html")
TIMEOUT = 30
SYMBOLS = {
    "SI=F": "قرارداد آتی نقره (SI=F؛ نه قیمت نقدی)",
    "SLV": "iShares Silver Trust (SLV)",
    "SIVR": "abrdn Physical Silver Shares ETF (SIVR)",
    "PSLV": "Sprott Physical Silver Trust (PSLV؛ ساختار تراست متفاوت است)",
}
PERIODS = [("۱ هفته معاملاتی", 5), ("۱ ماه معاملاتی", 21), ("۳ ماه معاملاتی", 63),
           ("۶ ماه معاملاتی", 126), ("۱ سال معاملاتی", 252)]


def fetch_history(symbol):
    query = urllib.parse.urlencode({"range": "5y", "interval": "1d", "events": "history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='=')}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FundBoardSilver/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        data = json.loads(response.read().decode())
    results = data.get("chart", {}).get("result") or []
    if not results:
        raise RuntimeError(f"No historical data for {symbol}: {data.get('chart', {}).get('error')}")
    node = results[0]
    quotes = node.get("indicators", {}).get("quote", [{}])[0]
    timestamps = node.get("timestamp", [])
    closes = quotes.get("close", [])
    rows = []
    for ts, close in zip(timestamps, closes):
        if close is not None and float(close) > 0:
            rows.append((datetime.fromtimestamp(ts, timezone.utc), float(close)))
    if len(rows) < 22:
        raise RuntimeError(f"Insufficient valid history for {symbol}: {len(rows)} observations")
    return rows


def pct(current, prior):
    return (current / prior - 1) * 100


def fa(s):
    return str(s).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TEHRAN)
    lines = ["📊 فاندبورد نقره | گزارش بازدهی جهانی نقره و ETFها",
             f"زمان تهیه گزارش به وقت تهران: {now:%Y-%m-%d %H:%M}",
             "روش: بازدهی از تغییر قیمت بسته‌شدن تعدیل‌نشده/سری قیمت Yahoo Finance محاسبه می‌شود؛ این ارقام لزوماً بازدهی کل با احتساب توزیع‌ها، کارمزد و مالیات نیستند.",
             "توجه: SI=F قرارداد آتی است و با قیمت نقدی نقره یکی نیست؛ ETFها/تراست‌ها نیز ساختار، هزینه و خطای تعقیب متفاوت دارند.", ""]
    successes = 0
    for symbol, label in SYMBOLS.items():
        lines.append(f"🔹 {label} ({symbol})")
        try:
            rows = fetch_history(symbol)
            successes += 1
            latest_time, latest = rows[-1]
            lines.append(f"آخرین مشاهده: {latest_time:%Y-%m-%d} UTC | قیمت پایانی: {latest:,.4f} USD")
            for name, n in PERIODS:
                if len(rows) > n:
                    old_time, old = rows[-1-n]
                    lines.append(f"• بازدهی {name}: {pct(latest, old):+.2f}% (از {old_time:%Y-%m-%d})")
                else:
                    lines.append(f"• بازدهی {name}: داده کافی نیست")
            lines.append(f"منبع داده تاریخی: https://finance.yahoo.com/quote/{symbol}/")
        except Exception as exc:
            lines.append(f"داده معتبر در دسترس نیست: {type(exc).__name__}: {exc}")
        lines.append("")
    lines += ["🧭 نحوه تفسیر", "• مقایسه منصفانه باید بازه و ارز پایه یکسان داشته باشد؛ بازدهی دلاری با بازدهی ریالی یکسان نیست.",
              "• برای ETFها، بازدهی قیمت با بازدهی کل فرق دارد. هزینه‌ها، توزیع‌ها، اختلاف NAV و بازار و ساختار محصول باید بررسی شوند.",
              "• AUM، موجودی فیزیکی و جریان خالص سرمایه در این گزارش به‌صورت خودکار حدس زده نمی‌شوند؛ فقط در صورت دسترسی به منبع رسمی و تاریخ‌دار گزارش خواهند شد.",
              "• این گزارش توصیفی است، نه پیش‌بینی و نه توصیه خرید یا فروش.", "Dry-run only: no Telegram message was sent."]
    report = "\n".join(lines)
    OUT.write_text(report, encoding="utf-8")
    print(report)
    print(f"SYMBOLS_WITH_DATA: {successes}/{len(SYMBOLS)}")
    print("TELEGRAM_MESSAGES_SENT: 0")
    if successes < 2:
        raise SystemExit("Fewer than two instruments returned usable history")


if __name__ == "__main__":
    main()
