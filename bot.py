
import json
import os
import urllib.parse
import urllib.request

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]

message = (
    "🟡 فاندبورد | تحلیل هوشمند طلا\n\n"
    "ربات تحلیل طلا با موفقیت راه‌اندازی شد.\n"
    "مرحله بعد: اتصال داده‌های اونس جهانی و طلای ایران.\n\n"
    "#طلا #اونس_جهانی"
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

payload = urllib.parse.urlencode({
    "chat_id": CHANNEL,
    "text": message
}).encode("utf-8")

request = urllib.request.Request(url, data=payload)

with urllib.request.urlopen(request, timeout=20) as response:
    result = json.loads(response.read().decode("utf-8"))

if not result.get("ok"):
    raise RuntimeError(f"Telegram error: {result}")

print("Message published successfully.")
