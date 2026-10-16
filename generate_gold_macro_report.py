"""Generate a sourced macro context draft for gold; never publishes to Telegram."""
import csv
import io
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
        "DFII10": ("بازده واقعی اوراق خزانه‌داری ۱۰ساله آمریکا", "درصد"),
        "DTWEXBGS": ("شاخص گسترده وزنی دلار آمریکا", "واحد شاخص"),
        "DFF": ("نرخ مؤثر وجوه فدرال آمریکا", "درصد"),
    }
    lines = [
        "🌐 فاندبورد طلا | بررسی عوامل بنیادی اونس جهانی",
        f"🕒 زمان تهیه گزارش به وقت ایران: {generated_at.astimezone(ZoneInfo('Asia/Tehran')).strftime('%Y-%m-%d %H:%M')}",
        "",
        "این گزارش زمینه اقتصاد کلان را بررسی می‌کند و به‌تنهایی سیگنال معاملاتی نیست.",
        "",
        "📌 آخرین داده‌های معتبر و تاریخ مشاهده",
    ]
    any_series = False
    for series_id, (label, unit) in labels.items():
        result = series_results.get(series_id)
        if not result:
            lines.append(f"- {label}: در دسترس نیست (دریافت منبع یا کنترل تازگی داده ناموفق بود)")
            continue
        any_series = True
        lines.append(
            f"- {label}: {result['value']:.3f} {unit}؛ تاریخ داده: {result['date']} "
            f"(قدمت داده: {result['age_days']} روز)."
        )
    lines.extend([
        "",
        "🧭 تفسیر: افزایش بازده واقعی یا تقویت دلار می‌تواند بر طلا فشار وارد کند؛ کاهش بازده واقعی یا تضعیف دلار ممکن است از طلا حمایت کند. شرایط بازار و انتظارات می‌توانند این رابطه‌ها را تغییر دهند. شاخص دلار این گزارش، شاخص گسترده تجاری است و با DXY تفاوت دارد.",
        "",
        "🏛️ اطلاعیه‌های اخیر فدرال رزرو (حداکثر ۱۴ روز اخیر)",
    ])
    if fed_items:
        for item in fed_items:
            lines.append(f"- {item['published_utc']}: {item['title']} — {item['url']}")
    else:
        lines.append("- اطلاعیه واجد شرایطی دریافت نشد؛ این موضوع به معنی نبود خبر مرتبط نیست.")
    lines.extend([
        "",
        "🔗 منابع:",
        "- FRED، بازده واقعی اوراق ۱۰ساله: https://fred.stlouisfed.org/series/DFII10",
        "- FRED، شاخص گسترده دلار: https://fred.stlouisfed.org/series/DTWEXBGS",
        "- FRED، نرخ مؤثر وجوه فدرال: https://fred.stlouisfed.org/series/DFF",
        "- اطلاعیه‌های فدرال رزرو: https://www.federalreserve.gov/feeds/press_all.xml",
        "",
        "محدودیت داده: جریان ETFها و خرید طلای بانک‌های مرکزی در این گزارش داده روزانه نیستند و باید با تاریخ انتشار معتبر گزارش شوند.",
        "⚠️ این گزارش آموزشی است و توصیه خرید یا فروش محسوب نمی‌شود."
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
