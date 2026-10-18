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
    output = (result.stderr or "") + (result.stdout or "")
    print(f"RUN {' '.join(command)} -> {result.returncode}")
    if result.returncode:
        print(output[-1500:])
        if command == ["publish_silver_prices.py"] and SCHEDULE == "briefing":
            print("WARNING: قیمت‌های لحظه‌ای در این اجرا تأیید نشد؛ جمع‌بندی بدون قیمت تأییدنشده ساخته می‌شود.")
            return ""
        if command == ["silver_specialist_posts.py"] and "429" in output and SCHEDULE in ("education", "briefing"):
            fallback = (
                "<b>📚 چگونه نقره را برای سرمایه‌گذاری ارزیابی کنیم؟</b>\\n\\n"
                "🥈 نقره هم فلزی گران‌بهاست و هم ماده‌ای پرکاربرد در صنعت؛ به همین دلیل، قیمت آن علاوه بر تقاضای سرمایه‌گذاری، "
                "از وضعیت تولید صنعتی، هزینه انرژی، عرضه معادن و شرایط مالی جهانی اثر می‌پذیرد.\\n\\n"
                "📊 برای ارزیابی روند، فقط تغییر یک روز را نبینید. قیمت را در چند بازه زمانی مقایسه کنید و بررسی کنید آیا "
                "حرکت کوتاه‌مدت با روند چندماهه هم‌جهت است یا خیر. بازده مثبت در یک بازه کوتاه، به‌تنهایی به معنی پایان روند نزولی نیست.\\n\\n"
                "⚖️ اگر از ابزارهای بورسی استفاده می‌کنید، ساختار محصول، هزینه سالانه، نقدشوندگی و فاصله قیمت بازار با ارزش دارایی‌ها "
                "را بررسی کنید. ابزار مبتنی بر قرارداد آتی الزاماً همان بازده نقره فیزیکی را ایجاد نمی‌کند.\\n\\n"
                "🧭 سناریوی صعودی زمانی اعتبار بیشتری دارد که بهبود تقاضا با نشانه‌های قیمتی تأیید شود؛ در سناریوی نزولی، "
                "ضعف تقاضای صنعتی یا تشدید شرایط مالی انقباضی می‌تواند فشار بیشتری ایجاد کند. هیچ شاخصی به‌تنهایی برای نتیجه‌گیری کافی نیست."
            )
            path = OUT / "specialist_post.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(fallback, encoding="utf-8")
            print("WARNING: منبع آموزش محدودیت درخواست داشت؛ از محتوای آموزشی پایدار استفاده شد.")
            return fallback
        if SCHEDULE == "briefing" and any(x in command[0] for x in ("silver_content_suite.py", "analyze_silver_news.py")) and "429" in output:
            print("WARNING: داده خبر به‌دلیل محدودیت درخواست در دسترس نبود؛ ادامه با سایر داده‌ها.")
            return ""
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
        with urllib.request.urlopen(req, timeout=35) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = result.get("result", {}).get("response") or result.get("result", {}).get("output_text")
        if not answer or not str(answer).strip():
            raise RuntimeError("هوش مصنوعی متن قابل انتشار تولید نکرد؛ پیام ارسال نشد.")
        return str(answer).strip()

    def sanitize(candidate):
        candidate = re.sub(r"(?i)https?://\\S+|خلاصه منبع[^\\n]*|منابع?:[^\\n]*", " ", candidate)
        candidate = re.sub(r"(?i)\\b(iShares Silver Trust|abrdn Physical Silver Shares ETF|Sprott Physical Silver Trust|ETF|ETFs|FundBoard|Reuters|Bloomberg|Fed)\\b", lambda m: {
            "ishares silver trust": "صندوق نقره", "abrdn physical silver shares etf": "صندوق نقره",
            "sprott physical silver trust": "تراست نقره", "etf": "صندوق قابل معامله", "etfs": "صندوق‌های قابل معامله",
            "fundboard": "فاندبورد", "reuters": "", "bloomberg": "", "fed": "فدرال رزرو"
        }.get(m.group(0).lower(), ""), candidate, flags=re.I)
        # Strip stray non-Persian scripts and any accidental English words, while preserving only essential tickers.
        candidate = re.sub(r"[\\u3400-\\u4dbf\\u4e00-\\u9fff\\u3040-\\u30ff\\uac00-\\ud7af\\u0400-\\u052f\\u0900-\\u097f]+", " ", candidate)
        allowed = {"SI=F": "قرارداد آتی نقره", "SLV": "صندوق نقره", "SIVR": "صندوق نقره", "PSLV": "تراست نقره", "RSI": "شاخص قدرت نسبی", "NAV": "ارزش خالص دارایی‌ها"}
        tokens = re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:=[A-Za-z])?(?![A-Za-z])", candidate)
        for token in sorted(set(tokens), key=len, reverse=True):
            replacement = allowed.get(token.upper(), "")
            candidate = re.sub(r"(?<![A-Za-z])" + re.escape(token) + r"(?![A-Za-z])", replacement, candidate, flags=re.I)
        candidate = re.sub(r"[ \\t]+", " ", candidate)
        candidate = re.sub(r" *\\n *", "\\n", candidate)
        candidate = re.sub(r"\\n{3,}", "\\n\\n", candidate)
        return candidate.strip()

    def quality_issues(candidate):
        issues = []
        if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|پیامی ارسال نشد|no telegram message|dry.?run|منابع:", candidate):
            issues.append("لینک، منبع یا متن داخلی باقی مانده")
        if any((0x3400 <= ord(ch) <= 0x9FFF) or (0x3040 <= ord(ch) <= 0x30FF) or (0xAC00 <= ord(ch) <= 0xD7AF) or (0x0400 <= ord(ch) <= 0x052F) or (0x0900 <= ord(ch) <= 0x097F) for ch in candidate):
            issues.append("نویسه بیگانه باقی مانده")
        if len(candidate) < 450 or sum(1 for ch in candidate if 0x0600 <= ord(ch) <= 0x06FF) < 140:
            issues.append("تحلیل فارسی کافی نیست")
        if len(candidate) > 2900:
            issues.append("متن را به حداکثر ۲۹۰۰ نویسه کاهش بده")
        if not re.search(r"[📊📉📈🥈🌍⚖️🧭💡⚠️📰🏭🔎]", candidate):
            issues.append("ایموجی مرتبط اضافه کن")
        return issues

    text = ask([{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 1400)
    text = sanitize(text)
    issues = quality_issues(text)
    for attempt in range(1, 3):
        if not issues:
            break
        repair_system = (
            'تو ویراستار نهایی یک کانال مالی فارسی هستی. نسخه نهایی را کاملاً به فارسی معیار بنویس. '
            'هیچ واژه یا نویسه چینی، ژاپنی، کره‌ای، روسی، هندی یا انگلیسی باقی نگذار، جز نمادهای مجاز در صورت ضرورت. '
            'متن را طبیعی و حرفه‌ای کن، ایموجی‌های مرتبط و محدود داشته باش، تیتر و نکات کلیدی روشن باشند. '
            'منبع، رسانه، لینک، متن داخلی یا پیش‌نمایش ننویس. عدد، واحد، تاریخ و علامت مثبت/منفی داده‌ها را عوض نکن و هیچ واقعیتی نساز. '
            'خروجی فقط متن نهایی قابل انتشار باشد.'
        )
        repair_user = (
            f'دسته محتوا: {label}\\nایرادهای لازم برای رفع: {"؛ ".join(issues)}\\n'
            f'داده‌های خام برای کنترل صحت: {source[:9000]}\\nمتن نیازمند اصلاح: {text}\\n'
            'بازنویسی کن و قبل از پاسخ، نبودن کلمات بیگانه و حفظ علامت بازده‌ها را کنترل کن.'
        )
        text = ask([{'role': 'system', 'content': repair_system}, {'role': 'user', 'content': repair_user}], 1400)
        text = sanitize(text)
        issues = quality_issues(text)
    if issues:
        raise RuntimeError('متن پس از سه مرحله بازبینی از کنترل کیفیت عبور نکرد؛ برای جلوگیری از انتشار محتوای خراب متوقف شد: ' + '؛ '.join(issues))
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
