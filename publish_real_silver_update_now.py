"""Publish a clean, live silver price update without redundant closing commentary."""
import os
import sys
import requests

def main():
    token = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_SILVER_BOT_TOKEN secret")
    import publish_silver_prices
    items = [publish_silver_prices.parse_page(*page) for page in publish_silver_prices.PAGES]
    message = publish_silver_prices.build_post(items)
    if len(message) > 4000:
        raise RuntimeError(f"Message too long for Telegram: {len(message)} characters")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": channel, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram did not confirm the message")
    print(f"REAL_POST_SENT channel={channel} message_id={data['result']['message_id']}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
