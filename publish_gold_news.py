import os
import json
import re
import urllib.request
import urllib.error

from analyze_gold_news import (
    fetch_news,
    analyze_news,
    select_relevant_news,
)


# ==========================================
# Configuration
# ==========================================

TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"

MAX_TELEGRAM_LENGTH = 3800
MIN_ARTICLES = 2
MIN_DISTINCT_SOURCES = 2
MAX_ARTICLES_FOR_ANALYSIS = 8


# ==========================================
# Prepare Telegram message
# ==========================================

def prepare_message(analysis, articles):
    message = analysis.strip()

    # Remove any AI-generated source list. Real RSS sources
    # will be appended below by this program.
    message = re.sub(
        r"(?is)\n\s*(?:منابع|منابع خبری|منابع منتخب)\s*:\s*.*$",
        "",
        message,
    )

    message = message.replace("**", "")
    message = re.sub(
        r"(?m)^\s*\*\s+",
        "• ",
        message,
    )
    message = re.sub(
        r"\n{3,}",
        "\n\n",
        message,
    ).strip()

    # Use only actual source URLs returned by Google News RSS.
    source_lines = []
    seen_sources = set()

    for article in articles:
        source = (
            article.get("source") or "منبع خبری"
        ).strip()

        title = (
            article.get("title") or ""
        ).strip()

        link = (
            article.get("link") or ""
        ).strip()

        source_key = source.casefold()

        if not link or source_key in seen_sources:
            continue

        seen_sources.add(source_key)

        source_lines.append(
            f"• {source}: {title}\n{link}"
        )

        if len(source_lines) >= 2:
            break

    source_section = ""

    if source_lines:
        source_section = (
            "\n\nمنابع منتخب:\n"
            + "\n\n".join(source_lines)
        )

    available_length = (
        MAX_TELEGRAM_LENGTH
        - len(source_section)
        - 2
    )

    if len(message) > available_length:
        message = message[
            :max(0, available_length - 35)
        ].rsplit(" ", 1)[0]

        message += (
            "\n\n[متن به دلیل محدودیت طول کوتاه شد.]"
        )

    return message + source_section


# ==========================================
# Publish to Telegram
# ==========================================

def publish_to_telegram(message):
    bot_token = os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )

    channel_id = os.environ.get(
        "TELEGRAM_CHANNEL_ID"
    )

    if not bot_token or not channel_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN or "
            "TELEGRAM_CHANNEL_ID is missing from GitHub Secrets."
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
            response_text = response.read().decode(
                "utf-8"
            )

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
            + json.dumps(
                result,
                ensure_ascii=False,
            )[:1500]
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
    relevant_articles = select_relevant_news(articles)

    print("Relevant articles:", len(relevant_articles))

    distinct_sources = {
        (
            article.get("source") or "Unknown"
        ).strip().casefold()
        for article in relevant_articles
    }

    print("Distinct sources:", len(distinct_sources))

    # Do not publish a weak analysis when the feed is sparse.
    if len(relevant_articles) < MIN_ARTICLES:
        print(
            "SKIP: Not enough relevant articles. "
            "Nothing was published."
        )
        return

    if len(distinct_sources) < MIN_DISTINCT_SOURCES:
        print(
            "SKIP: Too few distinct sources. "
            "Nothing was published."
        )
        return

    selected_articles = relevant_articles[
        :MAX_ARTICLES_FOR_ANALYSIS
    ]

    print("Generating Persian analysis...")

    analysis = analyze_news(selected_articles)

    if not analysis or not analysis.strip():
        raise RuntimeError(
            "The AI returned an empty analysis. "
            "Nothing was published."
        )

    message = prepare_message(
        analysis,
        selected_articles,
    )

    print("\nGenerated message preview:\n")
    print(message)

    publish_flag = os.environ.get(
        "PUBLISH_TO_TELEGRAM",
        "false",
    ).strip().lower()

    if publish_flag != "true":
        print(
            "\nTest mode: message was NOT sent to Telegram."
        )
        return

    print("\nPublishing to the configured Telegram channel...")

    publish_to_telegram(message)


if __name__ == "__main__":
    main()
