"""Generate all silver review previews, then send labeled samples to the requested Telegram channel."""
import html
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(".")
OUT = Path("silver_content_preview")
CHANNEL = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver").strip()
TOKEN = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
MAX_CHARS = 3600

def run(command, timeout=75):
    env = os.environ.copy()
    env["PUBLISH_TO_TELEGRAM"] = "false"
    p = subprocess.run([sys.executable, *command], text=True, capture_output=True,
                       timeout=timeout, env=env)
    print(f"COMMAND {' '.join(command)} exit={p.returncode}")
    if p.returncode:
        print((p.stderr or p.stdout)[-1800:])
    return (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")

def plain(text):
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", text)
    text = re.sub(r"(?i)<br\\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", text)
    return text.strip()

def read(path, fallback=""):
    p = Path(path)
    if p.exists() and p.stat().st_size:
        return plain(p.read_text(encoding="utf-8"))
    return plain(fallback)

def split_message(text, limit=MAX_CHARS):
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts, remaining = [], text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts

def telegram_send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHANNEL, "text": text,
                                 "disable_web_page_preview": True}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram API did not confirm message delivery")
    return data["result"]["message_id"]

def main():
    if not TOKEN:
        raise RuntimeError("Missing GitHub Actions secret TELEGRAM_SILVER_BOT_TOKEN")
    OUT.mkdir(parents=True, exist_ok=True)

    # Generate every preview first. Nothing is sent during these dry-run calls.
    price_log = run(["publish_silver_prices.py"])
    technical_log = run(["generate_silver_technical_report.py"])
    suite_log = run(["silver_content_suite.py"], timeout=90)
    periodic_log = run(["generate_silver_periodic_report.py"], timeout=90)
    macro_log = run(["generate_silver_macro_report.py"], timeout=90)
    news_log = run(["analyze_silver_news.py"], timeout=90)
    specialist_log = run(["silver_specialist_posts.py"])
    comparison_log = run(["generate_silver_gold_comparison.py"], timeout=90)
    briefing_log = run(["build_silver_daily_briefing.py"])

    candidates = [
        ("قیمت نقره و بازار فیزیکی", read(OUT / "silver_prices.html", price_log)),
        ("تحلیل تکنیکال", read(OUT / "technical.html", technical_log)),
        ("آموزش عوامل بنیادی و کلان", read(OUT / "macro_education.html", suite_log)),
        ("زمینه گزارش دوره‌ای", read(OUT / "periodic_context.html", periodic_log)),
        ("بازدهی جهانی و محصولات نقره", read(OUT / "periodic_returns.html", periodic_log)),
        ("اقتصاد کلان و عوامل بنیادی", read(OUT / "macro_report.html", macro_log)),
        ("رصد و تحلیل اخبار جهانی", read(OUT / "news_analysis.html", news_log)),
        ("پایش خبرهای تازه", read(OUT / "news_monitor.html", suite_log)),
        ("آموزش تخصصی", read(OUT / "specialist_post.html", specialist_log)),
        ("مقایسه طلا و نقره", read("silver_gold_comparison_preview.html", comparison_log)),
        ("گزارش ترکیبی روزانه", read(OUT / "daily_briefing.html", briefing_log)),
    ]
    # Remove duplicate/empty content and the internal diagnostic for Iranian silver funds.
    posts, seen = [], set()
    for label, body in candidates:
        if not body:
            raise RuntimeError(f"Preview is empty: {label}; aborting before Telegram publication.")
        body = re.sub(r"(?is).*?(تشخیص منبع صندوق‌های نقره ایران).*?(?=\n━━━━━━━━━━━━━━━━|$)", "", body)
        body = body.strip()
        if not body:
            raise RuntimeError(f"Preview became empty after exclusions: {label}")
        key = re.sub(r"\s+", " ", body)[:500]
        if key in seen:
            continue
        seen.add(key)
        for index, chunk in enumerate(split_message(body), 1):
            suffix = f" | بخش {index}" if len(split_message(body)) > 1 else ""
            posts.append((label + suffix, chunk))

    print(f"Prepared {len(posts)} labeled Telegram sample message(s); starting publication.")
    sent = []
    for index, (label, body) in enumerate(posts, 1):
        text = f"🧪 نمونه جهت تأیید | {label}\n\n{body}\n\n@FundBoard_Silver | فاندبورد نقره"
        message_id = telegram_send(text)
        sent.append(message_id)
        print(f"Telegram sample {index}/{len(posts)} sent; message_id={message_id}")
        time.sleep(1.1)
    print(f"SUCCESS: sent {len(sent)} review sample message(s) to {CHANNEL}.")
    print("Iranian silver funds were excluded. All samples were sent as plain text to avoid malformed HTML.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
