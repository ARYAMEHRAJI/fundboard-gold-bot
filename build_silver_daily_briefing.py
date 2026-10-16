"""Combine dry-run silver content modules into one preview; never publishes to Telegram."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")
OUTDIR = Path("silver_content_preview")
COMPARISON = Path("silver_gold_comparison_preview.html")
FOOTER = '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره\n‎داشبورد</a></b> <b><a href="https://t.me/FundBoard_Silver">سرمایه‌گذاری شما</a></b>'

def main():
    sections = [
        ("تحلیل تکنیکال", OUTDIR / "technical.html"),
        ("بررسی بنیادی", OUTDIR / "macro_education.html"),
        ("پایش خبرهای تازه", OUTDIR / "news_monitor.html"),
        ("زمینه گزارش دوره‌ای", OUTDIR / "periodic_context.html"),
    ]
    lines = [
        "🧭 <b>فاندبورد نقره | گزارش روزانه بازار</b>",
        f"🕒 زمان ساخت: {datetime.now(TEHRAN).strftime('%Y/%m/%d - %H:%M')} به وقت تهران",
        "",
        "این فایل پیش‌نمایش داخلی است و به تلگرام ارسال نمی‌شود.",
    ]
    missing = []
    for title, path in sections:
        if not path.is_file():
            missing.append(str(path))
            continue
        body = path.read_text(encoding="utf-8").strip()
        lines += ["", "━━━━━━━━━━━━", f"📌 <b>{title}</b>", "", body]
    if COMPARISON.is_file():
        lines += ["", "━━━━━━━━━━━━", "⚖️ <b>مقایسه طلا و نقره</b>", "", COMPARISON.read_text(encoding="utf-8").strip()]
    else:
        missing.append(str(COMPARISON))
    lines += ["", "⚠️ این خروجی فقط پیش‌نویس است؛ ارقام صندوق‌های نقره ایران تا زمان اعتبارسنجی منبع داده وارد نشده‌اند.", "", FOOTER]
    out = "\n".join(lines)
    target = OUTDIR / "daily_briefing.html"
    target.write_text(out + "\n", encoding="utf-8")
    print(f"DAILY_BRIEFING_DRY_RUN: {target}; characters={len(out)}; missing_sections={missing}; TELEGRAM_MESSAGES_SENT=0")
    if missing:
        raise SystemExit("Missing required sections: " + ", ".join(missing))

if __name__ == "__main__":
    main()
