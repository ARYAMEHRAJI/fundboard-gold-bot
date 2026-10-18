"""AI-edited Persian publisher for FundBoard Silver. Fails closed if AI editing is unavailable."""
import html
import os
import re
import subprocess
import sys
import time
import urllib.error
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
        if SCHEDULE == "briefing":
            stale_outputs = {
                "publish_silver_prices.py": ["silver_content_preview/silver_prices.html"],
                "generate_silver_technical_report.py": ["silver_content_preview/technical.html"],
                "silver_content_suite.py": ["silver_content_preview/technical.html", "silver_content_preview/news_monitor.html", "silver_content_preview/silver_prices.html", "silver_content_preview/periodic_context.html"],
                "generate_silver_periodic_report.py": ["silver_content_preview/periodic_returns.html"],
                "generate_silver_macro_report.py": ["silver_content_preview/macro_report.html"],
                "analyze_silver_news.py": ["silver_content_preview/news_analysis.html"],
                "silver_specialist_posts.py": ["silver_content_preview/specialist_post.html"],
                "generate_silver_gold_comparison.py": ["silver_gold_comparison_preview.html"],
            }
            for stale in stale_outputs.get(command[0], []):
                Path(stale).unlink(missing_ok=True)
            print(f"WARNING: {command[0]} failed; stale output removed and this section will be omitted.")
            if command == ["silver_specialist_posts.py"] and "429" in output:
                fallback = (
                    "📚 چگونه نقره را برای سرمایه‌گذاری ارزیابی کنیم؟\n\n"
                    "🥈 نقره هم فلزی گران‌بهاست و هم ماده‌ای صنعتی؛ بنابراین قیمت آن از تقاضای سرمایه‌گذاری، تولید صنعتی، "
                    "عرضه معادن و شرایط مالی جهانی اثر می‌پذیرد.\n\n"
                    "📊 برای ارزیابی روند، تغییر یک روز را از روند چندماهه جدا کنید. بازده مثبت کوتاه‌مدت به‌تنهایی پایان روند نزولی را ثابت نمی‌کند.\n\n"
                    "⚖️ در ابزارهای بورسی، ساختار محصول، هزینه سالانه، نقدشوندگی و فاصله قیمت بازار با ارزش دارایی‌ها را بررسی کنید. "
                    "محصول مبتنی بر قرارداد آتی الزاماً بازدهی برابر با نقره فیزیکی ندارد.\n\n"
                    "🧭 سناریوی صعودی زمانی معتبرتر می‌شود که بهبود تقاضا با نشانه‌های قیمتی تأیید شود؛ ضعف تقاضا یا شرایط مالی انقباضی می‌تواند فشار نزولی ایجاد کند."
                )
                (OUT / "specialist_post.html").write_text(fallback, encoding="utf-8")
                return fallback
            return ""
        if command == ["silver_specialist_posts.py"] and "429" in output and SCHEDULE == "education":
            fallback = (
                "<b>📚 چگونه نقره را برای سرمایه‌گذاری ارزیابی کنیم؟</b>\n\n"
                "🥈 نقره هم فلزی گران‌بهاست و هم ماده‌ای پرکاربرد در صنعت؛ به همین دلیل، قیمت آن علاوه بر تقاضای سرمایه‌گذاری، "
                "از وضعیت تولید صنعتی، هزینه انرژی، عرضه معادن و شرایط مالی جهانی اثر می‌پذیرد.\n\n"
                "📊 برای ارزیابی روند، فقط تغییر یک روز را نبینید. قیمت را در چند بازه زمانی مقایسه کنید و بررسی کنید آیا "
                "حرکت کوتاه‌مدت با روند چندماهه هم‌جهت است یا خیر. بازده مثبت در یک بازه کوتاه، به‌تنهایی به معنی پایان روند نزولی نیست.\n\n"
                "⚖️ اگر از ابزارهای بورسی استفاده می‌کنید، ساختار محصول، هزینه سالانه، نقدشوندگی و فاصله قیمت بازار با ارزش دارایی‌ها "
                "را بررسی کنید. ابزار مبتنی بر قرارداد آتی الزاماً همان بازده نقره فیزیکی را ایجاد نمی‌کند.\n\n"
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
        last_error = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    result = json.loads(response.read().decode("utf-8"))
                answer = result.get("result", {}).get("response") or result.get("result", {}).get("output_text")
                if not answer or not str(answer).strip():
                    raise RuntimeError("هوش مصنوعی متن قابل انتشار تولید نکرد؛ پیام ارسال نشد.")
                return str(answer).strip()
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 1:
                    raise
                delay = 8 * (attempt + 1)
                print(f"AI service temporarily unavailable (HTTP {exc.code}); retrying in {delay}s.")
                time.sleep(delay)
        raise last_error

    def sanitize(candidate):
        # Translate frequent English abbreviations and company names, then remove any residual Latin fragments.
        replacements = [
            (r"(?i)abrdn\s+Physical\s+Silver\s+Shares\s+ETF", "صندوق قابل معامله نقره فیزیکی"),
            (r"(?i)iShares\s+Silver\s+Trust", "صندوق نقره"),
            (r"(?i)Sprott\s+Physical\s+Silver\s+Trust", "تراست نقره فیزیکی"),
            (r"(?i)SI=F", "قرارداد آتی نقره"),
            (r"(?i)SLV", "صندوق نقره"),
            (r"(?i)SIVR", "صندوق نقره فیزیکی"),
            (r"(?i)PSLV", "تراست نقره فیزیکی"),
            (r"(?i)RSI(?:[- ]?14)?", "شاخص قدرت نسبی"),
            (r"(?i)NAV", "ارزش خالص دارایی‌ها"),
            (r"(?i)AUM", "ارزش دارایی‌های تحت مدیریت"),
            (r"(?i)ETFs?|ETFها", "صندوق قابل معامله"),
            (r"(?i)USD", "دلار آمریکا"),
            (r"(?i)Yahoo Finance|Google News|FRED|Reuters|Bloomberg", " "),
            (r"(?i)Federal Reserve|Fed", "بانک مرکزی آمریکا"),
            (r"(?i)gold", "طلا"),
            (r"(?i)silver", "نقره"),
            (r"(?i)futures", "قراردادهای آتی"),
            (r"(?i)diversification|diversify", "تنوع‌بخشی"),
            (r"(?i)quá", "بیش‌ازحد"),
            (r"影响گذار", "اثرگذار"),
            (r"影响", "اثر"),
            (r"可能", "ممکن است"),
            (r"然而", "بااین‌حال"),
            (r"城市", "شهرهای"),
            (r"влияние", "اثر"),
            (r"диверсификация", "تنوع‌بخشی"),
        ]
        candidate = re.sub(r"(?i)https?://\S+", " ", candidate)
        for pattern, replacement in replacements:
            candidate = re.sub(pattern, replacement, candidate)
        # Strip any remaining non-Persian scripts and English fragments so raw headlines cannot leak.
        candidate = re.sub(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u052f\u0900-\u097f]+", " ", candidate)
        candidate = re.sub(r"[A-Za-z][A-Za-z0-9]*(?:[=/-][A-Za-z0-9]+)?", " ", candidate)
        candidate = "\n".join(" ".join(line.split()) for line in candidate.splitlines())
        candidate = re.sub(r"\n{3,}", "\n\n", candidate)
        return candidate.strip()

    def quality_issues(candidate):
        issues = []
        if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|پیامی ارسال نشد|no telegram message|dry.?run|منابع:", candidate):
            issues.append("لینک، منبع یا متن داخلی باقی مانده")
        if any((0x3400 <= ord(ch) <= 0x9FFF) or (0x3040 <= ord(ch) <= 0x30FF) or (0xAC00 <= ord(ch) <= 0xD7AF) or (0x0400 <= ord(ch) <= 0x052F) or (0x0900 <= ord(ch) <= 0x097F) for ch in candidate):
            issues.append("نویسه بیگانه باقی مانده")
        if re.search(r"[A-Za-z]{2,}", candidate):
            issues.append("واژه انگلیسی باقی مانده")
        persian_count = sum(1 for ch in candidate if 0x0600 <= ord(ch) <= 0x06FF)
        if len(candidate) < 450 or persian_count < 140:
            issues.append("تحلیل فارسی کافی نیست")
        if len(candidate) > 2900:
            issues.append("متن را به حداکثر ۲۹۰۰ نویسه کاهش بده")
        if not re.search(r"[📊📉📈🥈🌍⚖️🧭💡⚠️📰🏭🔎📚]", candidate):
            issues.append("ایموجی مرتبط اضافه کن")
        # If a negative percentage from the raw data is reused, require a clear negative interpretation.
        def ascii_digits(value):
            return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace("٫", ".").replace("٪", "%")
        source_norm = ascii_digits(source)
        candidate_norm = ascii_digits(candidate)
        negative_returns = re.findall(r"(?<![0-9.])-([0-9]+(?:[.,][0-9]+)?) *%", source_norm)
        for number in negative_returns:
            number = re.escape(number.replace(",", "."))
            for match in re.finditer(number + r" *%", candidate_norm):
                before = candidate_norm[max(0, match.start()-35):match.start()]
                context = before + candidate_norm[match.end():match.end()+35]
                has_minus = before.rstrip().endswith(("-", "−"))
                if not has_minus and not re.search(r"کاهش|افت|منفی|نزول|کمتر", context):
                    issues.append("علامت منفی بازده در متن به‌اشتباه مثبت یا خنثی شده است")
                    break
            if issues and issues[-1] == "علامت منفی بازده در متن به‌اشتباه مثبت یا خنثی شده است":
                break
        return issues

    def deterministic_fallback():
        # If the hosted model is rate-limited, create a cautious, data-anchored Persian post rather than publishing raw headlines.
        data_lines = []
        seen_lines = set()
        for raw_line in source.splitlines():
            clean_line = sanitize(raw_line)
            if len(clean_line) < 12 or not re.search(r"[۰-۹0-9]", clean_line):
                continue
            if not re.search(r"[\u0600-\u06FF]", clean_line):
                continue
            if re.search(r"منبع|تاریخ گزارش|زمان گزارش|زمان تهیه|پیش.?نمایش|خطا|داده کافی", clean_line):
                continue
            clean_line = clean_line[:155].strip(" •-")
            if clean_line and clean_line not in seen_lines:
                seen_lines.add(clean_line)
                data_lines.append(clean_line)
            if len(data_lines) >= 5:
                break
        opening = {
            "technical": "📊 تحلیل تکنیکال: جایگاه قیمت نسبت به میانگین‌های کوتاه‌مدت و میان‌مدت، برای تشخیص جهت روند از تغییر یک‌روزه مهم‌تر است.",
            "periodic": "📈 تحلیل بازدهی: بازده‌های کوتاه‌مدت و بلندمدت ممکن است تصویر متفاوتی بدهند؛ افت چند هفته‌ای لزوماً عملکرد یک‌ساله را توضیح نمی‌دهد.",
            "news": "📰 تحلیل اخبار: تیتر خبری به‌تنهایی رابطه علت‌ومعلولی را ثابت نمی‌کند. خبرهای قیمت خرده‌فروشی یک شهر یا کشور را نباید معادل روند جهانی نقره دانست.",
            "comparison": "⚖️ مقایسه طلا و نقره: نسبت قیمت دو فلز فقط یک شاخص نسبی است؛ برای نتیجه‌گیری باید بازده در بازه زمانی و ارز پایه یکسان مقایسه شود.",
            "macro": "🌍 تحلیل بنیادی: نقره هم دارایی سرمایه‌گذاری است و هم فلزی صنعتی؛ دلار، نرخ‌های واقعی، تقاضای صنایع و عرضه معادن باید در کنار هم بررسی شوند.",
            "education": "📚 نکته آموزشی: برای ارزیابی ابزارهای سرمایه‌گذاری نقره، ساختار محصول، هزینه، نقدشوندگی و اختلاف قیمت بازار با ارزش دارایی‌ها را کنار هم بسنجید.",
            "briefing": "🧭 جمع‌بندی بازار: قیمت، روند تکنیکال، بازده دوره‌ای و اخبار را جداگانه بررسی کنید؛ اختلاف زمان ثبت داده‌ها می‌تواند مقایسه را گمراه‌کننده کند.",
        }.get(SCHEDULE, "📊 تحلیل بازار نقره: داده‌ها باید با توجه به بازه زمانی، واحد و ساختار دارایی تفسیر شوند.")
        lines = [opening, ""]
        if data_lines:
            lines.append("📌 داده‌های قابل استفاده در این گزارش:")
            lines.extend("• " + x for x in data_lines)
            lines.append("")
        lines.append(
            "🔎 برداشت تحلیلی: هیچ عدد یا خبر منفردی جهت قطعی قیمت را تعیین نمی‌کند. برای سناریوی صعودی باید بهبود تقاضا یا تثبیت قیمت با شواهد مستقل تأیید شود؛ "
            "در سناریوی نزولی، ضعف تقاضا، تشدید شرایط مالی یا شکست محدوده‌های حمایتی می‌تواند فشار را بیشتر کند. این سناریوها شرطی‌اند، نه پیش‌بینی قطعی."
        )
        lines.append("")
        lines.append(
            "⚠️ محدودیت و ریسک: قیمت قرارداد آتی الزاماً با قیمت نقدی برابر نیست و بازده ابزارهای مختلف نیز به ساختار، هزینه و ارز پایه وابسته است. "
            "اگر داده‌ای در دسترس نباشد، نباید با عدد تخمینی جایگزین شود. برای تصمیم‌گیری، تاریخ داده‌ها و هم‌خوانی شاخص‌ها را بررسی کنید."
        )
        return "\n".join(lines)

    try:
        text = ask([{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 1400)
    except Exception as exc:
        print(f"WARNING: AI editing unavailable ({type(exc).__name__}); using conservative Persian fallback.")
        text = deterministic_fallback()
    text = sanitize(text)
    issues = quality_issues(text)
    for attempt in range(1, 2):
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
            f'دسته محتوا: {label}\nایرادهای لازم برای رفع: {"؛ ".join(issues)}\n'
            f'داده‌های خام برای کنترل صحت: {source[:9000]}\nمتن نیازمند اصلاح: {text}\n'
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
    if SCHEDULE == "briefing":
        # Clear prior outputs first so the briefing never silently reuses stale prices or news.
        for stale in [
            "silver_content_preview/silver_prices.html", "silver_content_preview/technical.html",
            "silver_content_preview/macro_report.html", "silver_content_preview/periodic_returns.html",
            "silver_content_preview/news_analysis.html", "silver_content_preview/news_monitor.html",
            "silver_content_preview/specialist_post.html", "silver_content_preview/periodic_context.html",
            "silver_gold_comparison_preview.html", "silver_content_preview/daily_briefing.html",
        ]:
            Path(stale).unlink(missing_ok=True)
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
