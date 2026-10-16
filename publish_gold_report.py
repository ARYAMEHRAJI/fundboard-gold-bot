"""Publish a generated FundBoard Gold research draft to Telegram with safe HTML formatting."""
import argparse
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"
MAX_TELEGRAM_LENGTH = 3900
FOOTER = (
    '<b><a href="https://t.me/FundBoard_Gold">@FundBoard_Gold | فاندبورد طلا\n'
    '‎داشبورد</a></b> <b><a href="https://t.me/FundBoard_Gold">سرمایه‌گذاری شما</a></b>'
)
SECTION_PATTERNS = (
    r"^(?:📈|📊|🧭|🔎|🌐|🏛️|🏦|📌|⚠️|📚|🟡|💡|📰|📉|🔗)",
)


def format_body_line(line):
    line = line.strip()
    if not line:
        return ""
    safe = html.escape(line, quote=False)
    if any(re.match(pattern, line) for pattern in SECTION_PATTERNS):
        return f"<b>{safe}</b>"
    return safe


def prepare_message(text, generated_at=None):
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        raise ValueError("Report file is empty")
    title = lines.pop(0).strip()
    body_lines = []
    in_sources = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("🔗 منابع") or stripped.startswith("منابع:") or stripped.startswith("Sources:"):
            in_sources = True
            continue
        if in_sources:
            continue
        if stripped.startswith(("Dry-run only:", "این خروجی پیش‌نویس ترکیبی است",
                                "زمان ساخت (UTC):", "Generated at (UTC):",
                                "زمان تهیه گزارش", "🕒 زمان تهیه گزارش",
                                "زمان انتشار:", "🕒 زمان انتشار:")):
            continue
        # Keep the analysis text clean: no source URLs or source-link lines in Telegram.
        if "https://" in stripped or "http://" in stripped:
            continue
        body_lines.append(format_body_line(line))
    body = "\n".join(body_lines).strip()
    title_html = f"<b>{html.escape(title, quote=False)}</b>"
    content = f"{title_html}\n\n{body}\n\n{FOOTER}" if body else f"{title_html}\n\n{FOOTER}"
    if len(content) <= MAX_TELEGRAM_LENGTH:
        return content

    # Keep the title and footer intact; trim only the report body at a line boundary.
    budget = MAX_TELEGRAM_LENGTH - len(title_html) - len(FOOTER) - 8
    kept = []
    used = 0
    for line in body_lines:
        extra = len(line) + 1
        if used + extra > budget:
            break
        kept.append(line)
        used += extra
    while kept and not kept[-1].strip():
        kept.pop()
    kept.append("… ادامه جزئیات در گزارش بعدی/منبع رسمی")
    body = "\n".join(kept)
    content = f"{title_html}\n\n{body}\n\n{FOOTER}"
    if len(content) > MAX_TELEGRAM_LENGTH:
        raise ValueError("Unable to fit report safely within Telegram's message limit")
    return content


def send_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID GitHub secret")
    request = urllib.request.Request(
        TELEGRAM_API.format(token),
        data=urllib.parse.urlencode({
            "chat_id": channel_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {details[:1000]}") from exc
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected message: " + json.dumps(result, ensure_ascii=False))
    print(f"Telegram post published. message_id={result.get('result', {}).get('message_id', 'unknown')}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    text = Path(args.file).read_text(encoding="utf-8")
    message = prepare_message(text)
    print(f"Prepared Telegram HTML message: {len(message)} characters")
    publish = os.environ.get("PUBLISH_TO_TELEGRAM", "false").strip().lower() == "true"
    if not publish:
        print("Dry run: Telegram message was NOT sent.")
        print(message)
        return
    send_message(message)


if __name__ == "__main__":
    main()
