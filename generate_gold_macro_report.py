"""Generate a sourced macro context draft for gold; never publishes to Telegram."""
import csv
import io
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
FED_RSS = "https://www.federalreserve.gov/feeds/press_all.xml"
TIMEOUT = 20
MAX_SERIES_AGE_DAYS = 10
MAX_NEWS_AGE_DAYS = 14


def fetch_text(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "FundBoardGoldBot/1.0 (+market research draft)"}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_fred_csv(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("FRED CSV contained no observations")
    # FRED's missing values are commonly represented by a dot.
    valid = []
    for row in rows:
        try:
            day = date.fromisoformat(row["observation_date"])
            raw = next(value for key, value in row.items() if key != "observation_date")
            value = float(raw)
        except (KeyError, StopIteration, TypeError, ValueError):
            continue
        valid.append((day, value))
    if not valid:
        raise ValueError("FRED CSV contained no valid numeric observations")
    return sorted(valid)


def latest_fred_observation(text, today=None, max_age_days=MAX_SERIES_AGE_DAYS):
    today = today or datetime.now(timezone.utc).date()
    observations = parse_fred_csv(text)
    day, value = observations[-1]
    age = (today - day).days
    if age < 0:
        raise ValueError("FRED observation date is in the future")
    if age > max_age_days:
        raise ValueError(f"FRED observation is stale: {age} days old")
    return {"date": day.isoformat(), "value": value, "age_days": age}


def parse_fed_press_releases(xml_text, now=None, max_age_days=MAX_NEWS_AGE_DAYS, limit=5):
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(xml_text)
    items = []
    # RSS uses the standard item/title/link/pubDate elements.
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        raw_date = (item.findtext("pubDate") or "").strip()
        if not title or not link.startswith("https://"):
            continue
        try:
            published = parsedate_to_datetime(raw_date)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        age_days = (now - published).total_seconds() / 86400
        if age_days < -1 or age_days > max_age_days:
            continue
        items.append({
            "title": title,
            "url": link,
            "published_utc": published.isoformat(),
            "age_days": round(max(0, age_days), 1),
        })
    # Deduplicate links and titles; newest items first.
    unique, seen_links, seen_titles = [], set(), set()
    for item in sorted(items, key=lambda row: row["published_utc"], reverse=True):
        title_key = item["title"].casefold()
        if item["url"] in seen_links or title_key in seen_titles:
            continue
        seen_links.add(item["url"])
        seen_titles.add(title_key)
        unique.append(item)
    return unique[:limit]


def build_macro_snapshot(series_results, fed_items, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc)
    labels = {
        "DFII10": ("US 10-year real Treasury yield", "%"),
        "DTWEXBGS": ("US broad trade-weighted dollar index", "index points"),
        "DFF": ("Effective federal funds rate", "%"),
    }
    lines = [
        "🟡 FundBoard Gold | Macro context draft",
        f"Generated at (UTC): {generated_at.isoformat()}",
        "",
        "This is macro context for gold, not a standalone trading signal.",
        "",
        "📌 Latest validated observations",
    ]
    any_series = False
    for series_id, (label, unit) in labels.items():
        result = series_results.get(series_id)
        if not result:
            lines.append(f"- {label}: unavailable (source fetch or freshness check failed)")
            continue
        any_series = True
        lines.append(
            f"- {label}: {result['value']:.3f} {unit}; observation date: {result['date']} "
            f"(age: {result['age_days']} day(s))."
        )
    lines.extend([
        "",
        "How to read this (not a mechanical signal): rising real yields or a stronger dollar can weigh on gold, "
        "while falling real yields or a weaker dollar can support it. Market context and expectations can override "
        "these relationships. The broad dollar index is not the DXY index.",
        "",
        "🏛️ Recent Federal Reserve press releases (up to 14 days old)",
    ])
    if fed_items:
        for item in fed_items:
            lines.append(f"- {item['published_utc']}: {item['title']} — {item['url']}")
    else:
        lines.append("- No recent eligible releases were retrieved; this is not evidence that no relevant news exists.")
    lines.extend([
        "",
        "Sources:",
        "- FRED DFII10 (10-year inflation-indexed Treasury yield): https://fred.stlouisfed.org/series/DFII10",
        "- FRED DTWEXBGS (broad trade-weighted dollar index): https://fred.stlouisfed.org/series/DTWEXBGS",
        "- FRED DFF (effective federal funds rate): https://fred.stlouisfed.org/series/DFF",
        "- Federal Reserve press releases RSS: https://www.federalreserve.gov/feeds/press_all.xml",
        "",
        "Data limitations: ETF flows and central-bank gold purchases are not daily series here. "
        "They must be added from dated, authoritative releases and must not be presented as daily observations.",
        "⚠️ Educational market context only; not investment advice.",
    ])
    return "\n".join(lines)


def main():
    series_results = {}
    for series_id in ("DFII10", "DTWEXBGS", "DFF"):
        try:
            series_results[series_id] = latest_fred_observation(
                fetch_text(FRED_CSV.format(series=series_id))
            )
        except Exception as exc:
            # Keep the draft usable, but never silently substitute stale or guessed values.
            print(f"WARNING: {series_id} unavailable: {type(exc).__name__}: {exc}")
    fed_items = []
    try:
        fed_items = parse_fed_press_releases(fetch_text(FED_RSS))
    except Exception as exc:
        print(f"WARNING: Federal Reserve RSS unavailable: {type(exc).__name__}: {exc}")

    report = build_macro_snapshot(series_results, fed_items)
    with open("gold_macro_draft.txt", "w", encoding="utf-8") as output:
        output.write(report + "\n")
    print(report)
    print("\nDry-run only: no Telegram message was sent.")


if __name__ == "__main__":
    main()
