
import json
import urllib.request
from datetime import datetime, timezone, timedelta

IRAN_URL = (
    "https://raw.githubusercontent.com/iran-market/"
    "iran-market.github.io/main/data/popular.json"
)
GLOBAL_URL = "https://xaus.com/api/v1/spot?compact=1"
HISTORY_URL = "https://xaus.com/api/v1/history"


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FundBoardGoldBot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def iran_item(data, symbol):
    for item in data.get("data", []):
        if item.get("symbol") == symbol:
            return item
    raise ValueError(f"Missing market symbol: {symbol}")


def toman(value):
    return f"{round(value):,}".replace(",", "٬")


def signed_pct(value):
    return f"{value:+.2f}%".replace(".", "٫")


def main():
    iran = fetch_json(IRAN_URL)
    global_data = fetch_json(GLOBAL_URL)
    history_data = fetch_json(HISTORY_URL)

    usd = iran_item(iran, "USD_IRR_FREE")
    gold = iran_item(iran, "GOLD_18K_IRR")

    spot = float(global_data["spot_usd_oz"])
    points = history_data.get("points", [])

    if not points:
        raise ValueError("Gold history is empty")

    now = datetime.now(timezone.utc)
    today = now.date()

    # Find the latest historical close from a prior UTC date.
    previous = [
        p for p in points
        if p.get("d") and p.get("c")
        and datetime.strptime(p["d"], "%Y-%m-%d").date() < today
    ]

    if not previous:
        raise ValueError("No previous gold close found")

    prior = max(previous, key=lambda p: p["d"])
    prior_close = float(prior["c"])
    spot_change = (spot / prior_close - 1) * 100

    # Reject missing or stale core data.
    for item in (usd, gold):
        if item.get("stale") is True:
            raise ValueError(f"Stale Iranian data: {item['symbol']}")
        if not item.get("price") or not item.get("timestamp"):
            raise ValueError(f"Missing price or timestamp: {item['symbol']}")

    if global_data.get("data_state", {}).get("status") != "fresh":
        raise ValueError("Global gold spot is not marked fresh")

    usd_price = float(usd["price"])
    gold_price = float(gold["price"])
    usd_change = float(usd["change_pct"])
    gold_change = float(gold["change_pct"])

    # The Iranian feed uses IRT (toman) for these instruments.
    tehran_time = datetime.now(
        timezone(timedelta(hours=3, minutes=30))
    ).strftime("%H:%M")

    lines = [
        "🟡 فاندبورد | گزارش هوشمند بازار طلا",
        "",
        "🌍 اونس جهانی",
        f"قیمت لحظه‌ای: ${spot:,.2f}",
        f"تغییر نسبت به بسته‌شدن {prior['d']}: "
        f"{signed_pct(spot_change)}",
        "",
        "🇮🇷 بازار طلای ایران",
        f"دلار آزاد: {toman(usd_price)} تومان "
        f"({signed_pct(usd_change)})",
        f"طلای ۱۸ عیار: {toman(gold_price)} تومان "
        f"({signed_pct(gold_change)})",
        "",
        "📊 جمع‌بندی داده‌ها",
    ]

    if usd_change < 0 and gold_change < 0:
        lines.append(
            "دلار آزاد و طلای ۱۸ عیار در داده‌های ثبت‌شده "
            "هر دو کاهش داشته‌اند."
        )
    elif usd_change > 0 and gold_change > 0:
        lines.append(
            "دلار آزاد و طلای ۱۸ عیار در داده‌های ثبت‌شده "
            "هر دو افزایش داشته‌اند."
        )
    else:
        lines.append(
            "تغییرات دلار آزاد و طلای ۱۸ عیار هم‌جهت نیست؛ "
            "برای تحلیل علت، بررسی بیشتر لازم است."
        )

    lines.extend([
        "",
        "⚠️ قیمت‌ها مربوط به زمان ثبت هر منبع‌اند و "
        "ممکن است دقیقاً هم‌زمان نباشند.",
        f"زمان تولید گزارش: {tehran_time} تهران",
        "",
        "#طلا #اونس_جهانی #دلار #فاندبورد",
    ])

    print("\n".join(lines))


if __name__ == "__main__":
    main()
  
