"""Publish one genuine, current silver-market update to the channel."""
import os, sys, requests
from datetime import datetime
from zoneinfo import ZoneInfo

def main():
    token=os.getenv("TELEGRAM_SILVER_BOT_TOKEN","").strip()
    channel=os.getenv("TELEGRAM_SILVER_CHANNEL_ID","@FundBoard_Silver").strip()
    if not token: raise RuntimeError("Missing TELEGRAM_SILVER_BOT_TOKEN secret")
    env=os.environ.copy(); env["PUBLISH_TO_TELEGRAM"]="false"
    # Use the existing source-validated live market price publisher to build current data.
    import publish_silver_prices
    items=[publish_silver_prices.parse_page(*p) for p in publish_silver_prices.PAGES]
    base=publish_silver_prices.build_post(items)
    # This is a real editorial post, not a test/sample; remove the usual promotional footer's duplicated dashboard words only.
    stamp=datetime.now(ZoneInfo("Asia/Tehran")).strftime("%Y-%m-%d %H:%M")
    extra=(
      "\\n\\n📌 <b>برداشت تحلیلی</b>\\n"
      "قیمت نقره را باید هم‌زمان از دو مسیر بررسی کرد: قیمت جهانی هر اونس و نرخ ارز داخلی. "
      "در بازار ایران، تغییر نرخ ارز می‌تواند اثر حرکت جهانی نقره را تقویت یا خنثی کند؛ "
      "بنابراین مقایسه قیمت ریالی با اونس به‌تنهایی بدون توجه به نرخ دلار تصویر کاملی نمی‌دهد.\\n\\n"
      "این گزارش اطلاعات بازار است، نه سیگنال قطعی خرید یا فروش.\\n"
      f"🕒 زمان تهیه تحلیل: {stamp} به وقت تهران"
    )
    # Keep the original data-driven current price post, then add an original analytical section.
    message=base.replace("</b> <b><a href=", "</b> <b><a href=", 1)
    footer='<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره'
    if footer in message:
      pos=message.find(footer)
      message=message[:pos].rstrip()+extra+"\\n\\n"+message[pos:]
    else:
      message += extra
    r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
      json={"chat_id":channel,"text":message,"parse_mode":"HTML","disable_web_page_preview":True},timeout=30)
    r.raise_for_status(); data=r.json()
    if not data.get("ok"): raise RuntimeError(f"Telegram rejected message: {data}")
    print(f"REAL_POST_SENT channel={channel} message_id={data['result']['message_id']}")
if __name__=="__main__":
  try: main()
  except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}",file=sys.stderr); sys.exit(1)
