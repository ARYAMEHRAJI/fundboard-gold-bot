
import json
import os
import urllib.request
import urllib.error

account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
api_token = os.environ["CLOUDFLARE_API_TOKEN"]

url = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{account_id}/ai/run/@cf/qwen/qwen3.8-27b"
)

payload = {
    "messages": [
        {
            "role": "system",
            "content": (
                "تو تحلیلگر حرفه‌ای بازار طلا هستی. "
                "فقط به فارسی پاسخ بده."
            ),
        },
        {
            "role": "user",
            "content": (
                "یک پیام آزمایشی کوتاه برای کانال فاندبورد "
                "درباره اهمیت بررسی هم‌زمان اونس جهانی، "
                "دلار آزاد و طلای ۱۸ عیار بنویس. "
                "ادعای خبری یا قیمت ساختگی نداشته باش."
            ),
        },
    ]
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("success"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))

    print("CLOUDFLARE CONNECTION SUCCESSFUL")
    print(json.dumps(result.get("result", {}), ensure_ascii=False, indent=2))

except urllib.error.HTTPError as error:
    print("Cloudflare HTTP error:", error.code)
    print(error.read().decode("utf-8", errors="replace"))
    raise
  
