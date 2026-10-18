"""AI-edited Persian publisher for FundBoard Silver. Fails closed if AI editing is unavailable."""
import html
import os
import re
import subprocess
import sys
import urllib.request
import json
from pathlib import Path

import requests

OUT = Path("silver_content_preview")
TOKEN = os.getenv("TELEGRAM_SILVER_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("TELEGRAM_SILVER_CHANNEL_ID", "@FundBoard_Silver").strip()
SCHEDULE = os.getenv("SCHEDULE_KEY", "").strip()
MAX_LEN = 3500
FOOTER = '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره</a></b>'

JOBS = {
    "technical": {"label": "تحلیل تکنیکال نقره", "commands": [["generate_silver_technical_report.py"]], "file": "silver_technical_report.txt"},
    "news": {"label": "رصد و تحلیل اخبار نقره", "commands": [["analyze_silver_news.py"], ["silver_content_suite.py"]], "file": "news_analysis.html"},
    "periodic": {"label": "بازدهی دوره‌ای بازار جهانی نقره", "commands": [["generate_silver_periodic_report.py"]], "file": "periodic_returns.html"},
    "comparison": {"label": "مقایسه طلا و نقره", "commands": [["generate_silver_gold_comparison.py"]], "file": "../silver_gold_comparison_preview.html"},
    "macro": {"label": "تحلیل بنیادی و اقتصاد کلان نقره", "commands": [["generate_silver_macro_report.py"]], "file": "macro_report.html"},
    "education": {"label": "آموزش تخصصی نقره", "commands": [["silver_specialist_posts.py"]], "file": "specialist_post.html"},
    "briefing": {"label": "جمع‌بندی روزانه بازار نقره", "commands": [
        ["publish_silver_prices.py"], ["generate_silver_technical_report.py"], ["silver_content_suite.py"],
        ["generate_silver_periodic_report.py"], ["generate_silver_macro_report.py"], ["analyze_silver_news.py"],
        ["silver_specialist_posts.py"], ["generate_silver_gold_comparison.py"], ["build_silver_daily_briefing.py"]],
        "file": "daily_briefing.html"},
}

def run(command):
    env = os.environ.copy()
    env["PUBLISH_TO_TELEGRAM"] = "false"
    result = subprocess.run([sys.executable, *command], capture_output=True, text=True, timeout=100, env=env)
    print(f"RUN {' '.join(command)} -> {result.returncode}")
    if result.returncode:
        print((result.stderr or result.stdout)[-1500:])
        raise RuntimeError(f"Generator failed: {' '.join(command)}")
    return result.stdout

def plain_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", raw)
    raw = re.sub(r"(?i)<br\\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw).replace("\\r", "")
    raw = re.sub(r"[ \\t]+", " ", raw)
    raw = re.sub(r"\\n[ \\t]*\\n[ \\t]*\\n+", "\\n\\n", raw)
    return raw.strip()

def cloudflare_edit(source, label):
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        raise RuntimeError("برای تحلیل و بازنویسی هوش مصنوعی، کلیدهای Cloudflare تنظیم نشده‌اند؛ انتشار متوقف شد.")
    model = os.getenv("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    system = (
        "تو دبیر ارشد تحلیل بازار فلزات گران‌بها و نویسنده فارسی حرفه‌ای کانال تلگرام «فاندبورد نقره» هستی. "
        "متن ورودی خام و ممکن است شامل تیتر انگلیسی، نام رسانه، URL، برچسب فنی، تکرار، متن پیش‌نمایش یا داده ناقص باشد. "
        "آن را به یک پست نهایی، کاملاً فارسی، تحلیلی، داده‌محور، روان و حرفه‌ای تبدیل کن. "
        "اعداد و محاسبات موجود را حفظ کن و هرگز عدد، خبر، علت یا نتیجه‌ای جعل نکن. "
        "تیتر فارسی کوتاه و جذاب بنویس؛ بعد از داده‌ها توضیح بده این اعداد چه معنایی دارند، چه چیزی را نشان نمی‌دهند، "
        "سناریوی مثبت و منفی چه شرطی دارد و کدام ریسک‌ها مهم‌اند. تحلیل را به داده‌های واقعاً موجود گره بزن؛ "
        "اگر داده برای نتیجه‌گیری کافی نیست، دقیقاً بگو چه چیزی قابل نتیجه‌گیری نیست و به‌جای کلی‌گویی تحلیل معتبر ارائه کن. "
        "خبرهای انگلیسی را به فارسی ترجمه و مفهوم اقتصادی آن‌ها را تحلیل کن، اما نام رسانه، منبع، لینک، ارجاع، شناسه خبر، "
        "توضیح درباره ابزارها، خطاها، حالت آزمایشی، پیش‌نمایش، و عبارت «منبع» را در خروجی نیاور. "
        "نام نمادهای بورسی فقط وقتی لازم است به صورت نماد کوتاه در پرانتز بماند؛ اصطلاحات را فارسی توضیح بده. "
        "از تیترهای بولد به صورت متن ساده استفاده کن (بدون HTML و Markdown)، خط‌های کوتاه و پاراگراف‌های منظم بنویس. "
        "از تکرار داده بدون تحلیل، ادعای قطعیت، توصیه مستقیم خریدوفروش و جملات کلیشه‌ای پرهیز کن. "
        "خروجی فقط متن نهایی قابل انتشار باشد؛ هیچ مقدمه‌ای درباره کاری که انجام داده‌ای ننویس."
    )
    user = f"دسته محتوا: {label}\\n\\nمتن خام و داده‌های موجود:\\n{source[:18000]}\\n\\nیک پست نهایی فارسی و تحلیلی تولید کن."
    payload = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": 1600, "temperature": 0.25}
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=100) as response:
        result = json.loads(response.read().decode("utf-8"))
    text = result.get("result", {}).get("response") or result.get("result", {}).get("output_text")
    if not text or not str(text).strip():
        raise RuntimeError("هوش مصنوعی متن قابل انتشار تولید نکرد؛ پیام ارسال نشد.")
    text = str(text).strip()
    # Never allow source lists, URLs, raw English news headlines, or preview/debug artifacts through.
    if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|پیامی ارسال نشد|no telegram message|dry.?run|منابع:", text):
        raise RuntimeError("بازبینی خودکار خروجی هوش مصنوعی ناموفق بود؛ پیام ارسال نشد.")
    if sum(1 for ch in text if 0x0600 <= ord(ch) <= 0x06FF) < 120:
        raise RuntimeError("خروجی هوش مصنوعی تحلیل فارسی کافی ندارد؛ پیام ارسال نشد.")
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    persian = sum(1 for ch in text if 0x0600 <= ord(ch) <= 0x06FF)
    if latin > max(35, persian * 0.18):
        raise RuntimeError("در خروجی هوش مصنوعی متن لاتین بیش از حد مجاز است؛ پیام ارسال نشد.")
    return text

def html_format(text, label):
    # Remove any footer or duplicate generic headings returned by the model.
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if "FundBoard_Silver" in line or "فاندبورد نقره" in line and len(line) < 60:
            continue
        if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|dry.?run|منابع:", line):
            continue
        lines.append(line)
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        raise RuntimeError("متن نهایی پس از پاک‌سازی خالی است.")
    # Bold the post headline, plus key analytical lines and metric labels.
    out = [f"<b>{html.escape('📊 ' + label)}</b>", ""]
    first_content = True
    for line in lines:
        if not line:
            out.append("")
            continue
        safe = html.escape(line, quote=False)
        if first_content:
            safe = f"<b>{safe}</b>"
            first_content = False
        elif re.match(r"^(🔎|🧭|📌|📈|📉|⚖️|💡|سناریوی مثبت|سناریوی منفی|جمع‌بندی تحلیلی|برداشت تحلیلی|نتیجه‌گیری|نکته کلیدی|مهم‌ترین نکته)", line):
            safe = f"<b>{safe}</b>"
        else:
            safe = re.sub(r"^([•▪🔹-]\\s*[^:：]{2,35}[:：])", r"<b>\\1</b>", safe)
        out.append(safe)
    return "\\n".join(out).strip()

def split(text):
    # Split only on line boundaries; Telegram HTML parse mode is enabled for every part.
    result = []
    while len(text) > MAX_LEN:
        cut = text.rfind("\\n", 0, MAX_LEN)
        if cut < MAX_LEN // 2:
            cut = MAX_LEN
        result.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        result.append(text)
    return result

def main():
    if os.getenv("ALLOW_REVIEWED_SILVER_PUBLICATION", "").strip().lower() != "true":
        print("PUBLICATION_PAUSED: quality gate disabled.")
        return
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
        raw = plain_text(file_path.read_text(encoding="utf-8", errors="replace"))
    else:
        raw = plain_text(command_outputs[-1] if command_outputs else "")
    if not raw:
        raise RuntimeError(f"Generated output missing or empty: {file_path}")
    edited = cloudflare_edit(raw, job["label"])
    body = html_format(edited, job["label"])
    chunks = split(body)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for i, chunk in enumerate(chunks, 1):
        message = f"{chunk}\\n\\n{FOOTER}"
        response = requests.post(url, json={"chat_id": CHANNEL, "text": message, "parse_mode": "HTML",
            "disable_web_page_preview": True}, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError("Telegram did not confirm message delivery")
        print(f"Published {job['label']} to {CHANNEL}; message_id={data['result']['message_id']}")
    print(f"SUCCESS: {SCHEDULE}; AI_REWRITTEN=true; PERSIAN_ONLY_CHECK=passed; BOLD_LINKED_FOOTER=true")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
