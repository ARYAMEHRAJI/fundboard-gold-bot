
import os
import re
import json
import html
import urllib.parse
import urllib.request
import urllib.error

from analyze_gold_news import (
    fetch_news,
    analyze_news,
    select_relevant_news,
)


TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"

MAX_TELEGRAM_LENGTH = 3800
MIN_ARTICLES = 2
MIN_DISTINCT_SOURCES = 2

# این دو خط در انتهای تمام پست‌ها ثابت هستند.
FOOTER = (
    "<b>@FundBoard_Gold | فاندبورد طلا</b>\n\n"
    "<b>\u200eداشبورد سرمایه‌گذاری شما</b>"
)


def remove_markdown(text):
    """Remove common Markdown markers so they do not appear in Telegram."""
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def remove_sources_section(text):
    """
    Remove a trailing sources section if the model happens to generate one.
    The publisher does not add any source list.
    """
    lines = text.splitlines()
    kept = []

    source_heading = re.compile(
        r"^\s*(?:#{1,6}\s*)?"
        r"(?:منابع(?:\s+(?:خبر|منتخب|و\s‌?مراجع))?|"
        r"sources|references)\s*:?\s*$",
        flags=re.IGNORECASE,
    )

    for line in lines:
        if source_heading.match(line.strip()):
            break
        kept.append(line)

    return "\n".join(kept).strip()


def split_title_and_body(analysis):
    text = remove_markdown(analysis)
    text = remove_sources_section(text)

    lines = text.splitlines()

    while lines and not lines[0].strip():
        lines.pop(0)

    if not lines:
        raise RuntimeError("The generated analysis is empty.")

    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip()

    # Make sure the headline starts with a relevant emoji.
    emoji_pattern = re.compile(
        r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"
    )
    if not emoji_pattern.search(title):
        title = "🟡 " + title

    return title, body


def prepare_message(analysis):
    title, body = split_title_and_body(analysis)

    # Keep the body within Telegram's message-size limit.
    # Reserve space for the title, footer, HTML tags and spacing.
    fixed_text = title + "\n\n" + FOOTER
    max_body_chars = max(
        300,
        MAX_TELEGRAM_LENGTH - len(fixed_text) - 100
    )

    if len(body) > max_body_chars:
        body = body[:max_body_chars].rsplit(" ", 1)[0].rstrip()
        body += "…"

    # Escape all generated text before adding our own HTML tags.
    safe_title = html.escape(title, quote=False)
    safe_body = html.escape(body, quote=False)

    if safe_body:
        message = (
            f"<b>{safe_title}</b>\n\n"
            f"{safe_body}\n\n"
            f"{FOOTER}"
        )
    else:
        message = f"<b>{safe_title}</b>\n\n{FOOTER}"

    if len(message) > MAX_TELEGRAM_LENGTH:
        raise RuntimeError(
            f"Prepared Telegram message is too long: {len(message)} chars."
        )

    return message


def send_telegram_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()

    if not token or not channel_id:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID secret."
        )

    url = TELEGRAM_API.format(token)

    payload = {
        "chat_id": channel_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Telegram HTTP {exc.code}: {error_body[:1500]}"
        ) from exc

    if not result.get("ok"):
        raise RuntimeError(
            "Telegram rejected the message: "
            + json.dumps(result, ensure_ascii=False)
        )

    message_id = (
        result.get("result", {}).get("message_id", "unknown")
    )
    print(f"Message published successfully. Message ID: {message_id}")


def main():
    print("FundBoard Gold News Publisher")

    articles = select_relevant_news(fetch_news())

    distinct_sources = {
        article.get("source", "").strip().lower()
        for article in articles
        if article.get("source", "").strip()
    }

    print(f"Relevant articles selected: {len(articles)}")
    print(f"Distinct sources: {len(distinct_sources)}")

    if len(articles) < MIN_ARTICLES:
        print("SKIP: Not enough relevant articles.")
        return

    if len(distinct_sources) < MIN_DISTINCT_SOURCES:
        print("SKIP: Not enough distinct news sources.")
        return

    print("Generating Persian analysis...")
    analysis = analyze_news(articles)
    message = prepare_message(analysis)

    print("\nPrepared Telegram message preview:\n")
    print(message)
    print("\nPreview complete.")

    publish = os.environ.get(
        "PUBLISH_TO_TELEGRAM", "false"
    ).strip().lower() == "true"

    if not publish:
        print("Test mode: message was NOT sent to Telegram.")
        return

    send_telegram_message(message)


if __name__ == "__main__":
    main()
