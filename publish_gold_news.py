
import os
import json
import re
import urllib.request
import urllib.error

from analyze_gold_news import fetch_news, analyze_news


# ==========================================
# Configuration
# ==========================================

TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"

MAX_TELEGRAM_LENGTH = 3800

EXCLUDED_TITLE_TERMS = [
    "bangladesh",
    "ranchi",
    "bengaluru",
    "malda",
    "22 carat",
    "24 carat",
    "22-karat",
    "24-karat",
    "gold rate today in",
    "gold price in bangladesh",
]


# ==========================================
# Filter local gold-price news
# ==========================================

def select_relevant_news(articles):
    selected = []

    for article in articles:
        title = article.get("title", "").casefold()

        if any(term in title for term in EXCLUDED_TITLE_TERMS):
            continue

        selected.append(article)

    return selected


# ==========================================
# Prepare Telegram text
# ==========================================

def prepare_message(analysis):
    # The analysis is sent as plain text to avoid
    # Telegram Markdown parsing errors.
    message = analysis.strip()

    message = message.replace("**", "")
    message = re.sub(r"\n{3,}", "\n\n", message)

    if len(message) > MAX_TELEGRAM_LENGTH:
        message = message[:MAX_TELEGRAM_LENGTH - 30]
        message += "\n\nادامه تحلیل در دسترس نیست."

    return message


# ==========================================
# Publish to Telegram
# ==========================================

def publish_to_telegram(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")

    if not bot_token or not channel_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID "
            "is missing from GitHub Secrets."
        )

    endpoint = TELEGRAM_API.format(bot_token)

    payload = {
        "chat_id": channel_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            response_text = response.read().decode("utf-8")

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Telegram HTTP error {error.code}: "
            f"{error_body[:1500]}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Telegram connection error: {error}"
        ) from error

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Telegram returned invalid JSON."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            "Telegram could not publish the message: "
            + json.dumps(result, ensure_ascii=False)[:1500]
        )

    message_id = (
        result.get("result", {}).get("message_id")
    )

    print("Telegram publication successful.")
    print("Published message ID:", message_id)


# ==========================================
# Main
# ==========================================

def main():
    print("FundBoard Gold News Publisher")
    print("=" * 50)

    print("Fetching recent news...")

    articles = fetch_news()

    if not articles:
        raise RuntimeError(
            "No recent news was found. Nothing published."
        )

    relevant_articles = select_relevant_news(articles)

    print("Fetched articles:", len(articles))
    print("Relevant articles:", len(relevant_articles))

    if not relevant_articles:
        raise RuntimeError(
            "No relevant articles remained after filtering. "
            "Nothing published."
        )

    print("Generating Persian analysis...")

    analysis = analyze_news(relevant_articles)

    if not analysis or not analysis.strip():
        raise RuntimeError(
            "The AI returned an empty analysis. "
            "Nothing published."
        )

    message = prepare_message(analysis)

    print("\nGenerated message preview:\n")
    print(message)

    publish_flag = os.environ.get(
        "PUBLISH_TO_TELEGRAM", "false"
    ).lower()

    if publish_flag != "true":
        print(
            "\nTest mode: message was NOT sent to Telegram."
        )
        return

    print("\nPublishing to the configured Telegram channel...")
    publish_to_telegram(message)


if __name__ == "__main__":
    main()
  
