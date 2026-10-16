"""Combine validated technical and macro snapshots into one dry-run briefing."""
from datetime import datetime, timezone
from pathlib import Path

TECHNICAL_FILE = Path("gold_technical_draft.txt")
MACRO_FILE = Path("gold_macro_draft.txt")
PERIODIC_FILE = Path("gold_periodic_context_draft.txt")
OUTPUT_FILE = Path("gold_daily_briefing.txt")


def read_required(path):
    if not path.is_file():
        raise FileNotFoundError(f"Required draft is missing: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Required draft is empty: {path}")
    return content


def build_briefing(technical, macro, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc)
    timestamp = generated_at.astimezone(timezone.utc).isoformat()
    return "\n".join([
        "🟡 فاندبورد طلا | گزارش روزانه تکنیکال و بنیادی",
        f"زمان ساخت گزارش نهایی (UTC): {timestamp}",
        "",
        "این خروجی پیش‌نویس ترکیبی است. زمان مشاهده هر داده و محدودیت‌های منبع در بخش مربوطه حفظ شده‌اند.",
        "",
        "━━━━━━━━━━━━",
        "📈 بخش اول | تحلیل تکنیکال اونس جهانی",
        "",
        technical.strip(),
        "",
        "━━━━━━━━━━━━",
        "🌐 بخش دوم | زمینه بنیادی و اقتصاد کلان",
        "",
        macro.strip(),
        "",
        "━━━━━━━━━━━━",
        "📚 داده‌های دوره‌ای که هنوز در این نسخه به‌صورت خودکار وارد نشده‌اند",
        "- جریان ورود و خروج ETFهای طلای جهانی و تغییر موجودی آن‌ها: منبع رسمی شورای جهانی طلا؛ انتشار هفتگی/ماهانه و نه داده روزانه.",
        "  https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows",
        "- خرید و فروش طلای بانک‌های مرکزی: از گزارش‌های تاریخ‌دار شورای جهانی طلا استفاده شود؛ بسامد انتشار با داده روزانه متفاوت است.",
        "  https://www.gold.org/goldhub/data/gold-reserves",
        "تا زمان پیاده‌سازی و اعتبارسنجی دریافت خودکار این منابع، هیچ رقم یا جهت‌گیری درباره این دو شاخص حدس زده نشده است.",
        "",
        "⚠️ این گزارش آموزشی و اطلاعاتی است، توصیه خرید یا فروش نیست. سناریوهای تکنیکال مشروط‌اند و نباید به‌تنهایی مبنای تصمیم قرار گیرند.",
        "",
        "Dry-run only: no Telegram message was sent.",
    ])


def main():
    technical = read_required(TECHNICAL_FILE)
    macro = read_required(MACRO_FILE)
    periodic = read_required(PERIODIC_FILE)
    briefing = build_briefing(technical, macro) + "\n\n━━━━━━━━━━━━\n📚 بخش سوم | داده‌های دوره‌ای شورای جهانی طلا\n\n" + periodic
    OUTPUT_FILE.write_text(briefing + "\n", encoding="utf-8")
    print(briefing)


if __name__ == "__main__":
    main()
