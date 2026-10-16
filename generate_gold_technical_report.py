"""Generate a data-grounded XAU/USD technical snapshot (dry-run only)."""
import json
import urllib.request
from datetime import datetime, timezone

SPOT_URL = "https://xaus.com/api/v1/spot?compact=1"
HISTORY_URL = "https://xaus.com/api/v1/history"
TIMEOUT = 25


def fetch_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "FundBoardGoldBot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_closes(points):
    """Return sorted (date, close) pairs, ignoring malformed/duplicate rows."""
    by_date = {}
    for point in points:
        try:
            day = datetime.strptime(point["d"], "%Y-%m-%d").date()
            close = float(point["c"])
        except (KeyError, TypeError, ValueError):
            continue
        if close <= 0:
            continue
        by_date[day] = close
    return sorted(by_date.items())


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-period:]
    gains = sum(change for change in recent if change > 0) / period
    losses = -sum(change for change in recent if change < 0) / period
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    relative_strength = gains / losses
    return 100 - (100 / (1 + relative_strength))


def calculate_metrics(points, spot):
    rows = clean_closes(points)
    if len(rows) < 51:
        raise ValueError(f"Need at least 51 valid daily closes; got {len(rows)}")

    closes = [close for _, close in rows]
    latest_close = closes[-1]
    if spot <= 0:
        raise ValueError("Spot price must be positive")

    def change_from(index):
        base = closes[-1 - index]
        return (latest_close / base - 1) * 100

    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    latest_day = rows[-1][0].isoformat()

    return {
        "latest_date": latest_day,
        "latest_close": latest_close,
        "spot": spot,
        "return_7_sessions_pct": change_from(7),
        "return_30_sessions_pct": change_from(30),
        "sma20": sma20,
        "sma50": sma50,
        "rsi14": rsi(closes, 14),
        "spot_vs_latest_close_pct": (spot / latest_close - 1) * 100,
        "trend": "bullish" if sma20 > sma50 else "bearish" if sma20 < sma50 else "neutral",
    }


def format_pct(value):
    return f"{value:+.2f}%".replace(".", "٫")


def build_report(metrics):
    rsi_value = metrics["rsi14"]
    if rsi_value is None:
        rsi_text = "در دسترس نیست"
    else:
        rsi_text = f"{rsi_value:.1f}".replace(".", "٫")
    trend_text = {
        "bullish": "میانگین ۲۰روزه بالاتر از میانگین ۵۰روزه است",
        "bearish": "میانگین ۲۰روزه پایین‌تر از میانگین ۵۰روزه است",
        "neutral": "میانگین‌های ۲۰روزه و ۵۰روزه برابرند",
    }[metrics["trend"]]
    lines = [
        "🟡 فاندبورد طلا | نمای تکنیکال اونس جهانی",
        "",
        f"قیمت لحظه‌ای منبع: ${metrics['spot']:,.2f}",
        f"آخرین بسته‌شدن روزانه ({metrics['latest_date']}): ${metrics['latest_close']:,.2f}",
        f"فاصله قیمت لحظه‌ای با آخرین بسته‌شدن: {format_pct(metrics['spot_vs_latest_close_pct'])}",
        "",
        "📈 عملکرد بر اساس جلسات معاملاتی",
        f"۷ جلسه: {format_pct(metrics['return_7_sessions_pct'])}",
        f"۳۰ جلسه: {format_pct(metrics['return_30_sessions_pct'])}",
        "",
        "📊 شاخص‌های تکنیکال",
        f"SMA 20: ${metrics['sma20']:,.2f}",
        f"SMA 50: ${metrics['sma50']:,.2f}",
        f"RSI 14: {rsi_text}",
        f"وضعیت میانگین‌ها: {trend_text}",
        "",
        "⚠️ این گزارش صرفاً خلاصه‌ای از داده‌های قیمت است، نه توصیه خرید یا فروش. "
        "RSI به‌تنهایی سیگنال قطعی نیست و داده لحظه‌ای و بسته‌شدن روزانه ممکن است هم‌زمان نباشند.",
    ]
    return "\n".join(lines)


def main():
    spot_data = fetch_json(SPOT_URL)
    if spot_data.get("data_state", {}).get("status") != "fresh":
        raise ValueError("Spot source is not marked fresh")
    spot = float(spot_data["spot_usd_oz"])

    history_data = fetch_json(HISTORY_URL)
    points = history_data.get("points", [])
    metrics = calculate_metrics(points, spot)
    report = build_report(metrics)
    with open("gold_technical_draft.txt", "w", encoding="utf-8") as output:
        output.write(report + "\n")
    print(report)
    print("\nDry-run only: no Telegram message was sent.")


if __name__ == "__main__":
    main()
