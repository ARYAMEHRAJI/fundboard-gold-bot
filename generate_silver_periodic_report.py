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
    "SI=F": "قرارداد آتی نقره",
    "SLV": "صندوق نقره فیزیکی",
    "SIVR": "صندوق قابل معامله نقره فیزیکی",
    "PSLV": "تراست نقره فیزیکی",
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
    lines = ["📈 بازدهی نقره در بازه‌های زمانی مختلف",
             f"تاریخ گزارش به وقت تهران: {fa(now.strftime('%Y/%m/%d'))}", ""]
    successes = 0
    for symbol, label in SYMBOLS.items():
        try:
            rows = fetch_history(symbol)
            successes += 1
            latest_time, latest = rows[-1]
            lines.append(f"🥈 **{label}**")
            latest_date = fa(latest_time.strftime("%Y/%m/%d"))
            latest_price = fa(f"{latest:,.4f}")
            lines.append(f"آخرین قیمت پایانی در {latest_date}: **{latest_price} دلار**")
            for name, n in PERIODS:
                if len(rows) > n:
                    old_time, old = rows[-1-n]
                    change = pct(latest, old)
                    lines.append(f"• **بازده {name}:** {fa(f'{change:+.2f}')}٪")
                else:
                    lines.append(f"• بازده {name}: داده کافی نیست")
            lines.append("")
        except Exception:
            # Skip an instrument if its data feed failed; never publish exception text.
            continue
    if successes < 2:
        raise SystemExit("داده معتبر برای مقایسه بازدهی کمتر از دو ابزار بود؛ انتشار متوقف شد.")
    report = "\n".join(lines).strip()
    OUT.write_text(report, encoding="utf-8")
    print(report)
    print(f"SYMBOLS_WITH_DATA: {successes}/{len(SYMBOLS)}")
    print("TELEGRAM_MESSAGES_SENT: 0")


if __name__ == "__main__":
    main()
