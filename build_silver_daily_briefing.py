"""Combine dry-run silver modules into a daily briefing; no Telegram publishing."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN=ZoneInfo("Asia/Tehran")
OUTDIR=Path("silver_content_preview")
COMPARISON=Path("silver_gold_comparison_preview.html")
SECTIONS=[
 ("قیمت‌ها و شاخص‌های بازار","silver_prices.html"),
 ("تحلیل تکنیکال","technical.html"),
 ("عوامل بنیادی و اقتصاد کلان","macro_report.html"),
 ("بازدهی جهانی نقره و ETFها","periodic_returns.html"),
 ("تحلیل اخبار جهانی","news_analysis.html"),
 ("پایش خبرهای تازه","news_monitor.html"),
 ("آموزش و تحلیل تخصصی","specialist_post.html"),
 ("تشخیص منبع صندوق‌های نقره ایران","iran_silver_funds_diagnostic.json"),
 ("زمینه گزارش دوره‌ای","periodic_context.html"),
]
def main():
 lines=["🧭 <b>فاندبورد نقره | گزارش ترکیبی بازار</b>",
 f"🕒 زمان ساخت: {datetime.now(TEHRAN):%Y/%m/%d - %H:%M} به وقت تهران","",
 "این فایل پیش‌نمایش داخلی است و به تلگرام ارسال نمی‌شود.",""]
 found=0
 for label,filename in SECTIONS:
  p=OUTDIR/filename
  lines += [f"\n━━━━━━━━━━━━━━━━\n<b>{label}</b>"]
  if p.exists():
   text=p.read_text(encoding="utf-8").strip()
   lines.append(text[:10000]);found+=1
  else: lines.append("این ماژول هنوز خروجی تولید نکرده یا منبع آن در دسترس نبوده است.")
 if COMPARISON.exists():
  lines += ["\n━━━━━━━━━━━━━━━━\n<b>مقایسه طلا و نقره</b>",COMPARISON.read_text(encoding="utf-8")[:5000]]
 lines += ["","گزارش ترکیبی صرفاً پیش‌نمایش است؛ هیچ پیامی به تلگرام ارسال نشده است."]
 OUTDIR.mkdir(parents=True,exist_ok=True)
 OUTDIR.joinpath("daily_briefing.html").write_text("\n".join(lines),encoding="utf-8")
 print(f"SECTIONS_WITH_OUTPUT: {found}/{len(SECTIONS)}")
 print("\n".join(lines))
 print("TELEGRAM_MESSAGES_SENT: 0")
if __name__=="__main__":main()
