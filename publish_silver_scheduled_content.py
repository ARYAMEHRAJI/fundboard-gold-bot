"""Scheduled publisher for FundBoard Silver. Only the explicitly mapped schedule publishes a single post."""
import html
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(".")
OUT = Path("silver_content_preview")
TOKEN = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver").strip()
SCHEDULE = os.getenv("SCHEDULE_KEY", "").strip()
MAX_LEN = 3800

# GitHub schedule cron strings are UTC. The schedule label is passed explicitly by workflow.
JOBS = {
    "technical": {
        "label": "تحلیل تکنیکال نقره",
        "commands": [["generate_silver_technical_report.py"]],
        "file": "silver_technical_report.txt",
    },
    "news": {
        "label": "رصد و تحلیل اخبار نقره",
        "commands": [["analyze_silver_news.py"], ["silver_content_suite.py"]],
        "file": "news_analysis.html",
    },
    "periodic": {
        "label": "بازدهی دوره‌ای بازار جهانی نقره",
        "commands": [["generate_silver_periodic_report.py"]],
        "file": "periodic_returns.html",
    },
    "comparison": {
        "label": "مقایسه طلا و نقره",
        "commands": [["generate_silver_gold_comparison.py"]],
        "file": "../silver_gold_comparison_preview.html",
    },
    "macro": {
        "label": "تحلیل بنیادی و اقتصاد کلان نقره",
        "commands": [["generate_silver_macro_report.py"]],
        "file": "macro_report.html",
    },
    "education": {
        "label": "آموزش تخصصی نقره",
        "commands": [["silver_specialist_posts.py"]],
        "file": "specialist_post.html",
    },
    "briefing": {
        "label": "جمع‌بندی روزانه بازار نقره",
        "commands": [
            ["publish_silver_prices.py"],
            ["generate_silver_technical_report.py"],
            ["silver_content_suite.py"],
            ["generate_silver_periodic_report.py"],
            ["generate_silver_macro_report.py"],
            ["analyze_silver_news.py"],
            ["silver_specialist_posts.py"],
            ["generate_silver_gold_comparison.py"],
            ["build_silver_daily_briefing.py"],
        ],
        "file": "daily_briefing.html",
    },
}

def run(command):
    env = os.environ.copy()
    env["PUBLISH_TO_TELEGRAM"] = "false"
    result = subprocess.run([sys.executable, *command], capture_output=True, text=True,
                            timeout=100, env=env)
    print(f"RUN {' '.join(command)} -> {result.returncode}")
    if result.returncode:
        print((result.stderr or result.stdout)[-2000:])
        raise RuntimeError(f"Generator failed: {' '.join(command)}")
    return result.stdout

def strip_markup(raw):
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", raw)
    return raw.strip()

def split(text):
    result = []
    while len(text) > MAX_LEN:
        cut = text.rfind("\n", 0, MAX_LEN)
        if cut < MAX_LEN // 2:
            cut = MAX_LEN
        result.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        result.append(text)
    return result

def main():
    if SCHEDULE not in JOBS:
        raise RuntimeError(f"Unknown SCHEDULE_KEY: {SCHEDULE!r}")
    if not TOKEN:
        raise RuntimeError("Missing TELEGRAM_SILVER_BOT_TOKEN secret")
    job = JOBS[SCHEDULE]
    OUT.mkdir(parents=True, exist_ok=True)
    command_outputs = []
    for command in job["commands"]:
        command_outputs.append(run(command))
    file_path = Path(job["file"])
    if not file_path.is_absolute():
        file_path = OUT / file_path if not job["file"].startswith("../") else Path("silver_gold_comparison_preview.html")
    if file_path.exists() and file_path.stat().st_size > 0:
        body = strip_markup(file_path.read_text(encoding="utf-8", errors="replace"))
    else:
        # Some generators intentionally print their report to stdout instead of writing a file.
        body = strip_markup(command_outputs[-1] if command_outputs else "")
    if not body:
        raise RuntimeError(f"Expected generated output is missing or empty: {file_path}")
    # Do not allow the retired Iranian silver-fund diagnostic into scheduled posts.
    body = re.sub(r"(?is).*?تشخیص منبع صندوق‌های نقره ایران.*?(?=━━━━━━━━━━━━━━━━|$)", "", body).strip()
    if not body:
        raise RuntimeError("Generated content is empty after cleaning")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for part_number, chunk in enumerate(split(body), 1):
        prefix = f"📊 {job['label']}" + (f" — بخش {part_number}" if len(split(body)) > 1 else "")
        message = f"{prefix}\n\n{chunk}\n\n@FundBoard_Silver | فاندبورد نقره"
        response = requests.post(url, json={"chat_id": CHANNEL, "text": message,
                                            "disable_web_page_preview": True}, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError("Telegram did not confirm message delivery")
        print(f"Published {job['label']} to {CHANNEL}; message_id={data['result']['message_id']}")
    print(f"SUCCESS: {SCHEDULE}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
