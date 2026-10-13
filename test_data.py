
import json
import urllib.request
from datetime import datetime, timezone

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


def find_symbol(data, symbol):
    items = data.get("data", [])
    if isinstance(items, list):
        for item in items:
            if item.get("symbol") == symbol:
                return item
    return None


def main():
    print("=== FUND BOARD DATA TEST ===")
    print("UTC check:", datetime.now(timezone.utc).isoformat())

    print("\n[1] Iranian market")
    iran = fetch_json(IRAN_URL)

    for symbol in ("USD_IRR_FREE", "GOLD_18K_IRR"):
        item = find_symbol(iran, symbol)
        if item is None:
            print(f"{symbol}: NOT FOUND")
        else:
            print(symbol, json.dumps(item, ensure_ascii=False))

    print("\n[2] Global gold spot")
    global_data = fetch_json(GLOBAL_URL)
    state = global_data.get("data_state", {})

    print("Spot USD/oz:", global_data.get("spot_usd_oz"))
    print("Updated at:", global_data.get("updated_at"))
    print("Data status:", state.get("status"))
    print("Price as of:", global_data.get("price_as_of"))

    print("\n[3] Global gold history")
    history = fetch_json(HISTORY_URL)
    points = history.get("points", [])
    print("History points:", len(points))

    for point in points[-3:]:
        print(json.dumps(point, ensure_ascii=False))

    if not global_data.get("spot_usd_oz"):
        raise RuntimeError("Global gold price missing")

    if state.get("status") not in ("fresh", "stale"):
        raise RuntimeError("Global gold data unavailable")

    if not find_symbol(iran, "USD_IRR_FREE"):
        raise RuntimeError("Iranian dollar symbol missing")

    if not find_symbol(iran, "GOLD_18K_IRR"):
        raise RuntimeError("Iranian 18k gold symbol missing")

    print("\nDATA TEST PASSED")


if __name__ == "__main__":
    main()
  
