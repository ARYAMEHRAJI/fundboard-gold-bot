
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

API_URL = "https://cdn.tsetmc.com/api/Fund/GetFunds/5"
OUTPUT_JSON = Path("gold_funds_raw.json")
OUTPUT_REPORT = Path("gold_funds_diagnostic.txt")

TEHRAN = ZoneInfo("Asia/Tehran")

GOLD_KEYWORDS = (
    "طلا",
    "سکه",
    "شمش",
    "زر",
    "گلد",
)

def fetch_data():
    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0 FundBoardDataCheck/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(
                f"API returned HTTP {response.status}"
            )
        payload = response.read().decode("utf-8-sig")

    data = json.loads(payload)

    if not isinstance(data, dict):
        raise ValueError("Unexpected API response: expected JSON object")

    funds = data.get("funds")

    if not isinstance(funds, list):
        raise ValueError(
            "API response has no 'funds' list. "
            f"Available keys: {list(data.keys())}"
        )

    return funds, list(data.keys())


def find_names(record):
    """Collect likely name fields without assuming a fixed schema."""
    values = []

    for key, value in record.items():
        if isinstance(value, str):
            normalized_key = key.lower()

            if any(
                term in normalized_key
                for term in ("name", "title", "nam", "lval")
            ):
                values.append(value)

    return values


def contains_gold_keyword(record):
    searchable_text = " ".join(find_names(record)).casefold()
    return any(word.casefold() in searchable_text
               for word in GOLD_KEYWORDS)


def main():
    now = datetime.now(TEHRAN)
    print("MODE: DRY_RUN")
    print(f"TIME_TEHRAN: {now.isoformat()}")
    print(f"SOURCE: {API_URL}")

    funds, response_keys = fetch_data()
    selected = [
        fund for fund in funds
        if isinstance(fund, dict) and contains_gold_keyword(fund)
    ]

    result = {
        "mode": "dry_run",
        "source": API_URL,
        "retrieved_at_tehran": now.isoformat(),
        "response_keys": response_keys,
        "total_commodity_funds": len(funds),
        "matched_records": len(selected),
        "keyword_filter": list(GOLD_KEYWORDS),
        "warning": (
            "Keyword matches are candidates, not a verified official "
            "gold-fund classification. No returns, NAV premium, or "
            "capital flows are calculated in this diagnostic."
        ),
        "funds": selected,
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "FUNDBOARD GOLD — DATA DIAGNOSTIC",
        f"Retrieved: {now.isoformat()}",
        f"Source: {API_URL}",
        f"Total commodity records: {len(funds)}",
        f"Keyword matches: {len(selected)}",
        "",
        "RESPONSE KEYS:",
        ", ".join(response_keys),
        "",
    ]

    for index, fund in enumerate(selected, start=1):
        lines.append(f"--- Candidate {index} ---")
        lines.append(
            json.dumps(fund, ensure_ascii=False, indent=2)
        )
        lines.append("")

    lines.append(
        "No Telegram messages were sent. "
        "Keyword matches need verification."
    )

    OUTPUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"TOTAL_COMMODITY_FUNDS: {len(funds)}")
    print(f"KEYWORD_MATCHES: {len(selected)}")
    print(f"JSON_OUTPUT: {OUTPUT_JSON}")
    print(f"REPORT_OUTPUT: {OUTPUT_REPORT}")
    print("No Telegram messages were sent.")


if __name__ == "__main__":
    main()
