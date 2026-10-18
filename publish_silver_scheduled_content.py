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
FOOTER = '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره\n‎داشبوردسرمایه‌گذاری شما</a></b>'

JOBS = {
    "technical": {"label": "تحلیل تکنیکال نقره", "commands": [["generate_silver_technical_report.py"]], "file": "silver_technical_report.txt"},
    "news": {"label": "رصد و تحلیل اخبار نقره", "commands": [["analyze_silver_news.py"]], "file": "news_analysis.html"},
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
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw).replace("\r", "")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", raw)
    return raw.strip()

def cloudflare_edit(source, label):
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        raise RuntimeError("برای تحلیل و بازنویسی هوش مصنوعی، کلیدهای Cloudflare تنظیم نشده‌اند؛ انتشار متوقف شد.")
    model = os.getenv("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    system = (
        "تو دبیر ارشد تحلیل بازار نقره و ویراستار فارسی حرفه‌ای هستی. خروجی باید پستی آماده انتشار، روان، دقیق، توسعه‌یافته و واقعاً تحلیلی باشد، نه فهرست داده‌ها. "
        "متن ورودی خام و ممکن است شامل تیتر انگلیسی، نام رسانه، URL، برچسب فنی، تکرار، متن پیش‌نمایش یا داده ناقص باشد. "
        "یک تیتر کوتاه با ایموجی مرتبط بنویس؛ سپس ۳ تا ۵ پاراگراف تحلیلی منظم و مختصر. یک یا دو خط داده مهم را می‌توانی بیاوری و بعد تحلیل کن: تغییرات را مقایسه کن، شدت روند را توضیح بده، ارتباط داده‌ها و محدودیت نتیجه‌گیری را روشن کن و سناریوهای صعودی/نزولی را فقط به‌صورت شرطی شرح بده. هر پاراگراف فقط وقتی ایموجی مرتبط لازم دارد از ایموجی استفاده کند. "
        "اعداد کلیدی و به‌ویژه علامت مثبت/منفی، واحد و بازه زمانی را دقیقاً حفظ کن؛ هرگز بازده منفی را مثبت نکن یا علامت منفی را حذف نکن. اعداد را به شکل فارسی بنویس. هرگز عدد، خبر، علت، نقل‌قول یا پیش‌بینی نساز. در صورت زیاد بودن داده‌ها، فقط چند شاخص کلیدی را انتخاب کن و باقی را به‌درستی تحلیل کن. "
        "تیتر فارسی کوتاه و جذاب بنویس؛ بعد از داده‌ها توضیح بده این اعداد چه معنایی دارند، چه چیزی را نشان نمی‌دهند، "
        "سناریوی مثبت و منفی چه شرطی دارد و کدام ریسک‌ها مهم‌اند. تحلیل را به داده‌های واقعاً موجود گره بزن؛ "
        "اگر خبر فقط یک تیتر خام است و جزئیات قابل اتکا در ورودی وجود ندارد، جزئیات یا اثر ساختگی نساز؛ فقط مضمون قابل احراز را به فارسی خلاصه کن و صریح بگو از تیتر به‌تنهایی نمی‌توان اثر آن بر قیمت را قطعی دانست. از خبرهای محلی نامرتبط (مثلاً نرخ شهرهای هند یا ویتنام) نتیجه‌گیری درباره قیمت جهانی نقره نگیر. اگر داده ناکافی است، همین محدودیت را کوتاه بگو و بر داده‌های قیمت موجود تحلیل کن. "
        "خبرهای انگلیسی را به فارسی ترجمه و مفهوم اقتصادی آن‌ها را تحلیل کن، اما نام رسانه، منبع، لینک، ارجاع، شناسه خبر، "
        "توضیح درباره ابزارها، خطاها، حالت آزمایشی، پیش‌نمایش، و عبارت «منبع» را در خروجی نیاور. "
        "نام نمادهای بورسی فقط وقتی لازم است به صورت نماد کوتاه در پرانتز بماند؛ اصطلاحات را فارسی توضیح بده. "
        "هیچ نویسه چینی، ژاپنی، کره‌ای، روسی یا هندی و هیچ کلمه انگلیسی ننویس؛ تنها نمادهای ضروری SI=F، SLV، SIVR، PSLV، RSI و NAV مجازند و همان بار اول معنی فارسی‌شان گفته شود. به‌جای ETF بنویس «صندوق قابل معامله». به‌جای NAV بنویس «ارزش خالص دارایی‌ها». اعداد و تاریخ‌ها را فارسی و خوانا بنویس. از چند ایموجی مرتبط مانند 📊 📉 📈 🥈 🌍 ⚖️ 🧭 💡 ⚠️ 🏭 به‌جا استفاده کن. خروجی متن ساده بدون Markdown و HTML باشد. "
        "از تکرار داده بدون تحلیل، ادعای قطعیت، توصیه مستقیم خریدوفروش و جملات کلیشه‌ای پرهیز کن. "
        "خروجی فقط متن نهایی قابل انتشار باشد؛ هیچ مقدمه‌ای درباره کاری که انجام داده‌ای ننویس."
    )
    user = f"دسته محتوا: {label}\n\nمتن خام و داده‌های موجود:\n{source[:18000]}\n\nیک پست نهایی فارسی و تحلیلی تولید کن."
    def ask(messages, max_tokens=1200):
        payload = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.1}
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=75) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = result.get("result", {}).get("response") or result.get("result", {}).get("output_text")
        if not answer or not str(answer).strip():
            raise RuntimeError("هوش مصنوعی متن قابل انتشار تولید نکرد؛ پیام ارسال نشد.")
        return str(answer).strip()

    def quality_issues(candidate):
        issues = []
        if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|پیامی ارسال نشد|no telegram message|dry.?run|منابع:", candidate):
            issues.append("هیچ منبع، لینک، نام رسانه یا متن داخلی نیاور")
        forbidden_ranges = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0x3040, 0x30FF), (0xAC00, 0xD7AF),
                            (0x0400, 0x052F), (0x0900, 0x097F))
        if any(lo <= ord(ch) <= hi for ch in candidate for lo, hi in forbidden_ranges):
            issues.append("تمام واژه‌ها و نویسه‌های چینی، ژاپنی، کره‌ای، روسی و هندی را به فارسی طبیعی برگردان")
        latin_words = re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:=[A-Za-z])?(?![A-Za-z])", candidate)
        allowed_terms = {"SI=F", "SLV", "SIVR", "PSLV", "RSI", "NAV"}
        if any(word.upper() not in allowed_terms for word in latin_words):
            issues.append("تمام واژه‌های انگلیسی را فارسی کن؛ فقط نماد ضروری SI=F، SLV، SIVR، PSLV، RSI و NAV مجازند")
        if len(candidate) < 650 or sum(1 for ch in candidate if 0x0600 <= ord(ch) <= 0x06FF) < 180:
            issues.append("تحلیل فارسی را به اندازه کافی گسترش بده و ۳ تا ۵ پاراگراف تحلیلی بنویس")
        if len(candidate) > 3100:
            issues.append("متن را به حداکثر ۳۱۰۰ نویسه کاهش بده و تحلیل‌های تکراری را حذف کن")
        if re.search(r"(?i)\b(quá|diversification|ETF)\b|可能|影响", candidate):
            issues.append("اصطلاحات بیگانه را کاملاً به فارسی طبیعی تبدیل کن")
        return issues

    text = ask([{"role": "system", "content": system}, {"role": "user", "content": user}])
    issues = quality_issues(text)
    if issues:
        repair_system = (
            "تو ویراستار نهایی سخت‌گیر کانال مالی فارسی هستی. متن نامناسب را اصلاح کن. "
            "همه نویسه‌های چینی/ژاپنی/کره‌ای/روسی/هندی و واژه‌های انگلیسی را به فارسی روان تبدیل کن؛ "
            "هیچ منبع، نام رسانه، لینک یا متن داخلی نیاور. تیتر و چند نکته کلیدی باید برجسته‌پذیر باشند، "
            "چند ایموجی مرتبط به‌جا استفاده کن. اعداد و به‌ویژه علامت مثبت/منفی بازده‌ها را تغییر نده، "
            "هیچ داده‌ای نساز و تحلیل را حرفه‌ای نگه دار. خروجی فقط متن نهایی باشد."
        )
        repair_user = (
            f"دسته: {label}\nایرادهای شناسایی‌شده: {'؛ '.join(issues)}\n"
            f"داده‌های اصلی برای کنترل دقت:\n{source[:12000]}\n\n"
            f"متن نیازمند اصلاح:\n{text}\n\n"
            "متن را کامل اصلاح کن و فقط نسخه نهایی را برگردان."
        )
        text = ask([{"role": "system", "content": repair_system}, {"role": "user", "content": repair_user}], 1200)
        issues = quality_issues(text)
    if issues:
        raise RuntimeError("خروجی پس از یک دور اصلاح هنوز از کنترل کیفیت عبور نکرد؛ انتشار امن متوقف شد: " + "؛ ".join(issues))
    return text

def html_format(text, label):
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != '': lines.append('')
            continue
        if 'FundBoard_Silver' in line or ('فاندبورد نقره' in line and len(line) < 70): continue
        if re.search(r'(?i)https?://|خلاصه منبع|پیش.?نمایش|dry.?run|منابع:', line): continue
        if any((0x3400 <= ord(ch) <= 0x4DBF) or (0x4E00 <= ord(ch) <= 0x9FFF) or (0x3040 <= ord(ch) <= 0x30FF) or (0xAC00 <= ord(ch) <= 0xD7AF) for ch in line):
            raise RuntimeError('نویسه چینی/ژاپنی/کره‌ای شناسایی شد؛ انتشار متوقف شد.')
        lines.append(line)
    while lines and not lines[0].strip(): lines.pop(0)
    if not lines: raise RuntimeError('متن نهایی پس از پاک‌سازی خالی است.')
    headline = lines.pop(0).strip(' #*') or label
    if not re.search(r"[📊📉📈🥈🌍⚖️🧭💡⚠️📰🏭🔎]", headline):
        emoji = {"technical":"📊", "periodic":"📈", "news":"📰", "comparison":"⚖️",
                 "macro":"🌍", "education":"📚", "briefing":"🧭"}
        headline = f"{emoji.get(SCHEDULE, '📊')} {headline}"
    out = [f'<b>{html.escape(headline, quote=False)}</b>', '']
    important = re.compile(r'^(🔎|🧭|📌|📈|📉|⚖️|💡|🌍|🥈|⚠️|📰|🏭|📉|سناریوی مثبت|سناریوی منفی|جمع‌بندی|برداشت تحلیلی|نتیجه‌گیری|نکته کلیدی|مهم‌ترین نکته|چرا مهم است|چه چیزی را باید رصد کرد)')
    metric = re.compile(r'^([•▪🔹-]\s*[^:：]{2,35}[:：])')
    for line in lines:
        if not line: out.append(''); continue
        safe = html.escape(line, quote=False)
        if important.match(line): safe = f'<b>{safe}</b>'
        else:
            safe = metric.sub(r'<b>\1</b>', safe)
            safe = re.sub(r'^(نکته مهم|در سناریوی صعودی|در سناریوی نزولی|ریسک اصلی|جمع‌بندی نهایی)(:)', r'<b>\1\2</b>', safe)
        out.append(safe)
    result = '\n'.join(out).strip()
    if len(result) > MAX_LEN: raise RuntimeError('متن تحلیل از حد مجاز تلگرام بلندتر است؛ انتشار متوقف شد.')
    return result

def split(text):
    # Split only on line boundaries; Telegram HTML parse mode is enabled for every part.
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
    if len(body) > MAX_LEN:
        raise RuntimeError("متن طولانی‌تر از حد مجاز است؛ انتشار متوقف شد تا متن ناقص ارسال نشود.")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    message = f"{body}\n\n{FOOTER}"
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
