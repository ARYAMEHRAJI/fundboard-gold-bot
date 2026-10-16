
import json
import traceback
import urllib.request
import urllib.error

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

API_URL = "https://cdn.tsetmc.com/api/Fund/GetFunds/5"
OUTPUT_JSON = Path("gold_funds_raw.json")
OUTPUT_REPORT = Path("gold_funds_diagnostic.txt")
OUTPUT_ERROR = Path("gold_funds_error.txt")

TEHRAN = ZoneInfo("Asia/Tehran")

GOLD_KEYWORDS = (
    "طلا",
    "سکه",
    "شمش",
    "زر",
    "گلد",
)


def log(message):
    print(message, flush=True)


def write_error(message):
    OUTPUT_ERROR.write_text(message, encoding="utf-8")
    log(f"ERROR_FILE: {OUTPUT_ERROR}")


def fetch_data():
    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )

    log(f"REQUEST_URL: {API_URL}")
    log("REQUEST_STATUS: sending request")

    try:
        with urllib.request.urlopen(
            request,
            timeout=25,
        ) as response:
            status = response.status
            raw_data = response.read()

            log(f"HTTP_STATUS: {status}")
            log(f"RESPONSE_BYTES: {len(raw_data)}")

    except urllib.error.HTTPError as exc:
        details = (
            f"HTTP_ERROR: {exc.code}\n"
            f"URL: {API_URL}\n"
            f"REASON: {exc.reason}\n"
        )

        try:
            details += (
                "RESPONSE_BODY:\n"
                + exc.read(2000).decode("utf-8", errors="replace")
            )
        except Exception:
            pass

        write_error(details)
        raise

    except Exception as exc:
        details = (
            f"REQUEST_ERROR: {type(exc).__name__}: {exc}\n"
            f"URL: {API_URL}\n"
            f"{traceback.format_exc()}"
        )
        write_error(details)
        raise

    text = raw_data.decode("utf-8-sig", errors="replace")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        details = (
            f"JSON_ERROR: {exc}\n"
            f"RESPONSE_PREVIEW:\n{text[:2000]}\n"
        )
        write_error(details)
        raise

    if not isinstance(payload, dict):
        write_error(
            "UNEXPECTED_RESPONSE_TYPE: "
            f"{type(payload).__name__}\n"
            f"RESPONSE_PREVIEW:\n{text[:2000]}"
        )
        raise ValueError("API response is not a JSON object")

    funds = payload.get("funds")

    if not isinstance(funds, list):
        details = (
            "UNEXPECTED_API_SCHEMA\n"
            f"TOP_LEVEL_KEYS: {list(payload.keys())}\n"
            f"RESPONSE_PREVIEW:\n{text[:3000]}"
        )
        write_error(details)
        raise ValueError(
            "Expected a list in the 'funds' field; "
            f"received keys: {list(payload.keys())}"
        )

    return funds, list(payload.keys())


def get_candidate_names(record):
    names = []

    for key, value in record.items():
        if not isinstance(value, str):
            continue

        normalized_key = key.casefold()

        if any(
            term in normalized_key
            for term in ("name", "title", "nam", "lval")
        ):
            names.append(value)

    return names


def matches_gold_keyword(record):
    text = " ".join(get_candidate_names(record)).casefold()

    return any(
        keyword.casefold() in text
        for keyword in GOLD_KEYWORDS
    )


def main():
    now = datetime.now(TEHRAN)

    log("MODE: DRY_RUN")
    log(f"TIME_TEHRAN: {now.isoformat()}")
    log(f"SOURCE: {API_URL}")

    funds, response_keys = fetch_data()

    candidates = [
        item
        for item in funds
        if isinstance(item, dict)
        and matches_gold_keyword(item)
    ]

    result = {
        "mode": "dry_run",
        "source": API_URL,
        "retrieved_at_tehran": now.isoformat(),
        "response_keys": response_keys,
        "total_records": len(funds),
        "keyword_matches": len(candidates),
        "keywords": list(GOLD_KEYWORDS),
        "warning": (
            "Keyword matches are unverified candidates. "
            "No returns, NAV premium, or capital flows "
            "have been calculated."
        ),
        "funds": candidates,
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "FUNDBOARD GOLD - DATA DIAGNOSTIC",
        f"Retrieved: {now.isoformat()}",
        f"Source: {API_URL}",
        f"Total records: {len(funds)}",
        f"Keyword matches: {len(candidates)}",
        "",
        "RESPONSE KEYS:",
        ", ".join(response_keys),
        "",
    ]

    for index, item in enumerate(candidates, start=1):
        report_lines.extend([
            f"--- Candidate {index} ---",
            json.dumps(item, ensure_ascii=False, indent=2),
            "",
        ])

    report_lines.append(
        "No Telegram messages were sent. "
        "Candidates require verification."
    )

    OUTPUT_REPORT.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    log(f"TOTAL_RECORDS: {len(funds)}")
    log(f"KEYWORD_MATCHES: {len(candidates)}")
    log(f"JSON_OUTPUT: {OUTPUT_JSON}")
    log(f"REPORT_OUTPUT: {OUTPUT_REPORT}")
    log("RESULT: SUCCESS")
    log("No Telegram messages were sent.")


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        error_details = (
            f"FAILED: {type(exc).__name__}: {exc}\n\n"
            f"{traceback.format_exc()}"
        )

        log(error_details)

        try:
            write_error(error_details)
        except Exception as save_exc:
            log(
                "ERROR_FILE_WRITE_FAILED: "
                f"{type(save_exc).__name__}: {save_exc}"
            )

        raise
