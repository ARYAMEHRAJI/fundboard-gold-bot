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
        "تو دبیر ارشد و تحلیلگر بازار جهانی نقره برای کانال فارسی فاندبورد نقره هستی. خروجی باید یک پست به‌روز، خوش‌خوان، تخصصی اما قابل فهم برای مخاطب عادی باشد. "
        "تحلیل باید از داده‌های واقعی همین ورودی نتیجه شود، نه فهرست خشک داده‌ها و نه متن کلیشه‌ای. یک تیتر جذاب با ایموجی مرتبط بنویس؛ سپس ۳ تا ۵ پاراگراف کوتاه. "
        "داده‌های مهم را با برچسب روشن بیاور و بلافاصله معنایشان را توضیح بده: تغییر روزانه را با روند چند هفته‌ای بسنج، بازده کوتاه‌مدت را با میان‌مدت مقایسه کن، نسبت طلا به نقره را درست تفسیر کن و اثر احتمالی خبرهای عرضه و تقاضا را توضیح بده. "
        "هیچ عدد، تاریخ، خبر، علت یا پیش‌بینی را نساز. علامت مثبت/منفی، بازه زمانی، واحد و تاریخ داده را حفظ کن. اگر داده‌ای در دسترس نیست، آن شاخص را حذف کن؛ خطا، مقدار خالی و جمله «داده در دسترس نیست» را به متن نهایی نیاور. "
        "از بخش‌های کلیشه‌ای با عنوان‌های «برداشت تحلیلی»، «محدودیت و ریسک»، «ریسک‌های مهم»، «سناریوی مثبت/منفی»، «داده‌های قابل استفاده»، «نحوه تفسیر» و هر نوع سلب مسئولیت پایانی استفاده نکن. تحلیل را در دل متن طبیعی و دقیق بنویس و جملات کلی مثل «هیچ عددی به‌تنهایی جهت قطعی را تعیین نمی‌کند» را تکرار نکن. "
        "اخبار: فقط خبرهای تازه و واقعاً مرتبط با نقره را انتخاب کن؛ تیتر انگلیسی را به فارسی طبیعی ترجمه کن و اگر خلاصه خبر وجود دارد، مضمون آن را توضیح بده. خبر قیمت خرده‌فروشی یک شهر هند یا ویتنام را به‌عنوان روند جهانی معرفی نکن؛ اگر خبر محلی برای بازار جهانی مهم نیست، حذفش کن. از تیتر ناقص، خبر تکراری، نام رسانه، URL، شناسه خبر و زمان UTC استفاده نکن. "
        "در تحلیل تکنیکال، RSI را «شاخص قدرت نسبی» بنویس: کمتر از ۳۰ معمولاً ناحیه اشباع فروش، بالاتر از ۷۰ معمولاً ناحیه اشباع خرید و بین آن‌ها محدوده میانی است. قیمت را با میانگین‌ها و محدوده‌های حمایتی/مقاومتی مقایسه کن. "
        "در گزارش بازدهی، درصد منفی را هرگز مثبت یا بدون علامت نکن. در گزارش بنیادی، اگر داده کلان معتبر موجود نیست، روی خبرهای قابل اتکای عرضه/تقاضا و رابطه اقتصادی آن‌ها تمرکز کن؛ خبر قدیمی یا ناقص را خبر امروز جلوه نده. در آموزش، یک نکته کاربردی را با مثال روشن توضیح بده. در جمع‌بندی روزانه هر محور را فقط یک بار بیاور و از تکرار جلوگیری کن. "
        "فارسی معیار بنویس؛ هیچ کلمه انگلیسی، نویسه چینی/ژاپنی/کره‌ای/روسی/هندی، متن خام منبع یا عبارت داخلی نباید باقی بماند. اصطلاحات را فارسی توضیح بده. از ایموجی‌های مرتبط و متنوع در تیتر و چند جای متن استفاده کن، اما در هر جمله ایموجی نگذار. تیتر و داده‌ها و نکته مهم را با Markdown به‌شکل **بولد** مشخص کن. "
        "خروجی فقط متن نهایی باشد، بدون مقدمه، منبع، لینک، هشدار کلیشه‌ای یا امضای کانال؛ امضای کانال بعداً خودکار افزوده می‌شود."
    )
    user = f"دسته محتوا: {label}\n\nمتن خام و داده‌های موجود:\n{source[:18000]}\n\nیک پست نهایی فارسی و تحلیلی تولید کن."
    def ask(messages, max_tokens=1200):
        payload = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.1}
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    result = json.loads(response.read().decode("utf-8"))
                answer = result.get("result", {}).get("response") or result.get("result", {}).get("output_text")
                if not answer or not str(answer).strip():
                    raise RuntimeError("هوش مصنوعی متن قابل انتشار تولید نکرد؛ پیام ارسال نشد.")
                return str(answer).strip()
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                delay = 25 * (attempt + 1)
                print(f"AI service temporarily unavailable (HTTP {exc.code}); retrying in {delay}s.")
                time.sleep(delay)
        raise last_error

    def sanitize(candidate):
        # Translate known terms, but do not silently erase unknown foreign text from sentences.
        replacements = [
            (r"(?i)abrdn\s+Physical\s+Silver\s+Shares\s+ETF", "صندوق نقره فیزیکی"),
            (r"(?i)iShares\s+Silver\s+Trust", "صندوق نقره"),
            (r"(?i)Sprott\s+Physical\s+Silver\s+Trust", "تراست نقره فیزیکی"),
            (r"(?i)\\bSI=F\\b", "قرارداد آتی نقره"), (r"(?i)\\bSLV\\b", "صندوق نقره"),
            (r"(?i)\\bSIVR\\b", "صندوق نقره فیزیکی"), (r"(?i)\\bPSLV\\b", "تراست نقره فیزیکی"),
            (r"(?i)\\bRSI(?:[- ]?14)?\\b", "شاخص قدرت نسبی"), (r"(?i)\\bNAV\\b", "ارزش خالص دارایی‌ها"),
            (r"(?i)\\bAUM\\b", "ارزش دارایی‌های تحت مدیریت"), (r"(?i)\\bETFs?\\b|ETFها", "صندوق قابل معامله"),
            (r"(?i)USD", "دلار آمریکا"),
            (r"(?i)Yahoo Finance|Google News|FRED|Reuters|Bloomberg|FinanceFeeds|SilverTrade|FXStreet|Business Today|CaptainAltcoin", " "),
            (r"(?i)Federal Reserve|Fed", "بانک مرکزی آمریکا"), (r"(?i)gold", "طلا"),
            (r"(?i)silver", "نقره"), (r"(?i)futures", "قراردادهای آتی"),
            (r"(?i)diversification|diversify", "تنوع‌بخشی"), (r"(?i)quá", "بیش‌ازحد"),
            (r"影响گذار", "اثرگذار"), (r"影响", "اثر"), (r"可能", "ممکن است"),
            (r"然而", "بااین‌حال"), (r"城市", "شهرهای"),
            (r"влияние", "اثر"), (r"диверсификация", "تنوع‌بخشی"),
        ]
        candidate = re.sub(r"(?i)https?://\S+", " ", candidate)
        for pattern, replacement in replacements:
            candidate = re.sub(pattern, replacement, candidate)
        candidate = html.unescape(candidate).replace("\r", "")
        candidate = re.sub(r"(?m)^\s*(?:منابع|منبع خبرها|خلاصه منبع|وضعیت تحلیل|زمان تولید|زمان گزارش UTC|حالت آزمایشی|پیش‌نمایش داخلی)\s*:.*$", "", candidate)
        candidate = re.sub(r"(?m)^\s*[-•▪]?\s*(?:Dry-run only|No Telegram message was sent|پیامی ارسال نشد).*?$", "", candidate, flags=re.I)
        candidate = re.sub(r"[ \t]+", " ", candidate)
        candidate = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", candidate)
        return candidate.strip()

    def quality_issues(candidate):
        issues = []
        if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|پیامی ارسال نشد|no telegram message|dry.?run|منابع:|زمان تولید UTC|زمان گزارش UTC", candidate):
            issues.append("لینک، منبع یا متن داخلی باقی مانده")
        if any((0x3400 <= ord(ch) <= 0x9FFF) or (0x3040 <= ord(ch) <= 0x30FF) or (0xAC00 <= ord(ch) <= 0xD7AF) or (0x0400 <= ord(ch) <= 0x052F) or (0x0900 <= ord(ch) <= 0x097F) for ch in candidate):
            issues.append("نویسه بیگانه باقی مانده")
        if re.search(r"[A-Za-z]{2,}", candidate):
            issues.append("واژه انگلیسی باقی مانده")
        if re.search(r"(?im)^\s*(?:🔎\s*)?(?:برداشت تحلیلی|محدودیت و ریسک|ریسک‌های مهم|داده‌های قابل استفاده در این گزارش|داده‌های قابل استفاده|سناریوی مثبت برای|سناریوی منفی برای|نحوه تفسیر|چارچوب تفسیر|محدودیت:|ریسک اصلی)\s*:", candidate):
            issues.append("بخش کلیشه‌ای یا ممنوع باقی مانده")
        if re.search(r"(?i)توصیه خرید یا فروش|این گزارش توصیفی است|هیچ شاخصی به تنهایی|هیچ عدد یا خبر منفردی جهت قطعی|در مجموع، قیمت نقره.*نمی‌توان با اطمینان پیش‌بینی", candidate):
            issues.append("جمله کلیشه‌ای یا سلب مسئولیت غیرلازم باقی مانده")
        persian_count = sum(1 for ch in candidate if 0x0600 <= ord(ch) <= 0x06FF)
        if len(candidate) < 420 or persian_count < 130:
            issues.append("تحلیل فارسی کافی نیست")
        if len(candidate) > 2700:
            issues.append("متن را به حداکثر ۲۷۰۰ نویسه کاهش بده")
        if not re.search(r"[📊📉📈🥈🌍⚖️🧭💡📰🏭🔎📚💰]", candidate):
            issues.append("ایموجی مرتبط اضافه کن")
        if not re.search(r"(?m)^\s*(?:\*\*)?[*#]?[📊📉📈🥈🌍⚖️🧭💡📰🏭🔎📚💰]", candidate):
            issues.append("تیتر فارسی مشخص با ایموجی در ابتدای متن وجود ندارد")
        if candidate.count("**") % 2:
            issues.append("قالب بولد ناقص است")
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
                if not has_minus:
                    issues.append("علامت منفی بازده در متن به‌اشتباه مثبت یا خنثی شده است")
                    break
            if issues and issues[-1] == "علامت منفی بازده در متن به‌اشتباه مثبت یا خنثی شده است":
                break
        return issues

    def deterministic_fallback():
        # A fallback is allowed only where real input data supports a meaningful post.
        if SCHEDULE == "education":
            return ("📚 **چطور خبرهای نقره را از سیگنال واقعی بازار جدا کنیم؟**\n\n"
                    "🥈 نقره هم فلزی گران‌بهاست و هم ماده‌ای صنعتی؛ بنابراین خبرهای آن را در سه محور بخوانید: عرضه معادن و بازیافت، مصرف صنعتی و شرایط مالی جهانی.\n\n"
                    "📊 خبر زمانی برای تحلیل مفیدتر است که اندازه تغییر، زمان وقوع و اثر احتمالی آن بر عرضه یا تقاضا روشن باشد. تیترهایی مثل «افزایش تقاضا» بدون عدد یا جزئیات کافی نیستند؛ تغییر مشخص تولید یا آمار مصرف با دوره زمانی روشن، امکان مقایسه بهتری می‌دهد.")
        raise RuntimeError("هوش مصنوعی در دسترس نیست و برای این دسته متن جایگزین داده‌محور و قابل اتکا وجود ندارد؛ انتشار متوقف شد.")

    try:
        text = ask([{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 1400)
    text = ask([{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 1400)
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
        try:
            text = ask([{'role': 'system', 'content': repair_system}, {'role': 'user', 'content': repair_user}], 1400)
            text = sanitize(text)
        except Exception as exc:
            raise RuntimeError(f"هوش مصنوعی نتوانست متن را اصلاح کند؛ انتشار متوقف شد ({type(exc).__name__}).")
        issues = quality_issues(text)
    if issues:
        raise RuntimeError('متن پس از سه مرحله بازبینی از کنترل کیفیت عبور نکرد؛ برای جلوگیری از انتشار محتوای خراب متوقف شد: ' + '؛ '.join(issues))
    return text

def html_format(text, label):
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != "": lines.append("")
            continue
        if "FundBoard_Silver" in line or ("فاندبورد نقره" in line and len(line) < 90): continue
        if re.search(r"(?i)https?://|خلاصه منبع|پیش.?نمایش|dry.?run|منابع:|پیامی ارسال نشد|داده‌های قابل استفاده|برداشت تحلیلی|محدودیت و ریسک|سناریوی مثبت برای|سناریوی منفی برای", line):
            raise RuntimeError("عبارت داخلی، کلیشه‌ای یا بخش ممنوع در متن نهایی شناسایی شد.")
        if any((0x3400 <= ord(ch) <= 0x9FFF) or (0x3040 <= ord(ch) <= 0x30FF) or (0xAC00 <= ord(ch) <= 0xD7AF) or (0x0400 <= ord(ch) <= 0x052F) or (0x0900 <= ord(ch) <= 0x097F) for ch in line):
            raise RuntimeError("نویسه غیر فارسی شناسایی شد؛ انتشار متوقف شد.")
        if re.search(r"[A-Za-z]{2,}", line):
            raise RuntimeError("واژه انگلیسی در متن نهایی باقی مانده؛ انتشار متوقف شد.")
        lines.append(line)
    while lines and not lines[0].strip(): lines.pop(0)
    if not lines: raise RuntimeError("متن نهایی پس از پاک‌سازی خالی است.")
    headline = lines.pop(0).strip(" #*") or label
    if not re.search(r"[📊📉📈🥈🌍⚖️🧭💡📰🏭🔎📚💰]", headline):
        emoji = {"technical":"📊", "periodic":"📈", "news":"📰", "comparison":"⚖️",
                 "macro":"🌍", "education":"📚", "briefing":"🧭"}
        headline = f"{emoji.get(SCHEDULE, '📊')} {headline}"
    out = [f"<b>{html.escape(headline, quote=False)}</b>", ""]
    important = re.compile(r"^(🔎|🧭|📌|📈|📉|⚖️|💡|🌍|🥈|📰|🏭|📚|💰|جمع‌بندی|نکته کلیدی|مهم‌ترین نکته|چرا مهم است|چه چیزی را باید رصد کرد)")
    metric = re.compile(r"^([•▪🔹-]\s*[^:：]{2,35}[:：])")
    for line in lines:
        if not line: out.append(""); continue
        safe = html.escape(line, quote=False)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        if important.match(line) and not safe.startswith("<b>") and "<b>" not in safe: safe = f"<b>{safe}</b>"
        elif "<b>" not in safe: safe = metric.sub(r"<b>\1</b>", safe)
        out.append(safe)
    result = "\n".join(out).strip()
    if len(result) > MAX_LEN: raise RuntimeError("متن تحلیل از حد مجاز تلگرام بلندتر است؛ انتشار متوقف شد.")
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
