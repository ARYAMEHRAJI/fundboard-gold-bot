"""FundBoard Silver content suite: dry-run only, no Telegram publishing.
Mirrors the gold project content families with silver-specific data and safeguards.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")
OUTPUT = Path("silver_content_preview")
TIMEOUT = 25
YAHOO = {
    "silver": "https://query1.finance.yahoo.com/v8/finance/chart/SI=F?range=6mo&interval=1d",
    "gold": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=6mo&interval=1d",
}
NEWS_QUERY = '"silver price" OR "silver futures" OR "silver demand" OR "silver supply" OR "solar silver" when:1d'
NEWS_URL = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
    {"q": NEWS_QUERY, "hl": "en-US", "gl": "US", "ceid": "US:en"}
)

def fa(value):
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FundBoardSilver/1.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))

def fetch_history(symbol):
    data = fetch_json(YAHOO[symbol])
    results = data.get("chart", {}).get("result") or []
    if not results:
        raise RuntimeError(f"No Yahoo Finance data for {symbol}")
    node = results[0]
    quote = node.get("indicators", {}).get("quote", [{}])[0]
    closes = [float(v) for v in quote.get("close", []) if v is not None]
    highs = [float(v) for v in quote.get("high", []) if v is not None]
    lows = [float(v) for v in quote.get("low", []) if v is not None]
    if len(closes) < 55 or len(highs) < 20 or len(lows) < 20:
        raise RuntimeError(f"Insufficient daily history for {symbol}")
    return {"closes": closes, "highs": highs, "lows": lows, "currency": node.get("meta", {}).get("currency", "USD")}

def sma(values, period):
    return sum(values[-period:]) / period if len(values) >= period else None

def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    diffs = [values[i] - values[i-1] for i in range(1, len(values))]
    window = diffs[-period:]
    gains = sum(max(x, 0) for x in window) / period
    losses = sum(max(-x, 0) for x in window) / period
    if losses == 0:
        return 100.0 if gains else 50.0
    return 100 - 100 / (1 + gains / losses)

def fmt(value, decimals=2):
    return f"{value:,.{decimals}f}"

def jalali_date(dt):
    gy, gm, gd = dt.year, dt.month, dt.day
    gdm = [31,28,31,30,31,30,31,31,30,31,30,31]
    jdm = [31,31,31,31,31,31,30,30,30,30,30,29]
    gy2, gm2, gd2 = gy-1600, gm-1, gd-1
    dn = 365*gy2 + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400
    for i in range(gm2): dn += gdm[i]
    if gm2 > 1 and ((gy%4==0 and gy%100!=0) or gy%400==0): dn += 1
    dn += gd2 - 79
    jnp = dn // 12053; dn %= 12053
    jy = 979 + 33*jnp + 4*(dn//1461); dn %= 1461
    if dn >= 366:
        jy += (dn-1)//365; dn = (dn-1)%365
    jm = 1
    for days in jdm:
        if dn < days: break
        dn -= days; jm += 1
    return f"{jy:04d}/{jm:02d}/{dn+1:02d}"

def stamp():
    now = datetime.now(TEHRAN)
    return f"{fa(jalali_date(now))} - {fa(now.strftime('%H:%M'))}"

def technical_post():
    d = fetch_history("silver")
    c, h, l = d["closes"], d["highs"], d["lows"]
    last, prev = c[-1], c[-2]
    m20, m50, rv = sma(c,20), sma(c,50), rsi(c)
    change = (last / prev - 1) * 100
    support, resistance = min(l[-20:]), max(h[-20:])
    if last > m20 > m50: trend = "صعودی بر اساس هم‌جهتی قیمت و میانگین‌ها"
    elif last < m20 < m50: trend = "نزولی بر اساس هم‌جهتی قیمت و میانگین‌ها"
    else: trend = "ترکیبی؛ میانگین‌ها جهت یکسانی ندارند"
    momentum = "بالا" if rv >= 70 else "پایین" if rv <= 30 else "میانه"
    return "\n".join([
        "📊 <b>تحلیل تکنیکال نقره جهانی</b>", f"🕒 زمان گزارش: {stamp()} به وقت تهران", "",
        f"• قیمت تسویه آخرین جلسه: <b>{fa(fmt(last))} دلار</b>",
        f"• تغییر نسبت به جلسه قبل: <b>{fa(f'{change:+.2f}')}٪</b>",
        f"• میانگین ۲۰روزه: {fa(fmt(m20))} دلار | میانگین ۵۰روزه: {fa(fmt(m50))} دلار",
        f"• RSI-14: {fa(fmt(rv,1))} ({momentum})", f"• محدوده کمینه ۲۰ جلسه: {fa(fmt(support))} دلار",
        f"• محدوده بیشینه ۲۰ جلسه: {fa(fmt(resistance))} دلار", "", f"برداشت روند: {trend}.",
        "سناریوی مثبت نیازمند تثبیت بالای محدوده مقاومت است؛ شکست حمایت می‌تواند فشار نزولی را بیشتر کند.",
        "این شاخص‌ها بر داده‌های روزانه قرارداد آتی نقره مبتنی‌اند و قیمت لحظه‌ای نقدی ایران نیستند.",
        "", footer()
    ])

def fetch_news():
    request = urllib.request.Request(NEWS_URL, headers={"User-Agent":"Mozilla/5.0 FundBoardSilver/1.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        root = ET.fromstring(response.read())
    now = datetime.now(timezone.utc)
    articles, seen = [], set()
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        raw_date = item.findtext("pubDate") or ""
        try:
            dt = parsedate_to_datetime(raw_date).astimezone(timezone.utc)
        except Exception:
            continue
        if not title or not link.startswith("http") or title in seen or dt < now-timedelta(hours=36) or dt > now+timedelta(minutes=10):
            continue
        seen.add(title)
        source = item.findtext("source") or urllib.parse.urlparse(link).netloc
        articles.append({"title": title, "link": link, "source": source, "published": dt.isoformat()})
    return sorted(articles, key=lambda a:a["published"], reverse=True)[:8]

def news_post(articles):
    if not articles:
        return "📰 <b>پایش خبرهای نقره</b>\nدر بازه بررسی‌شده خبر تاریخ‌دار و قابل‌اعتبارسنجی پیدا نشد؛ برای جلوگیری از انتشار خبر کهنه، پستی تولید نشد."
    lines = ["📰 <b>مهم‌ترین خبرهای تازه نقره</b>", f"🕒 زمان پایش: {stamp()}", ""]
    for a in articles[:5]:
        lines.append(f"• <a href=\"{a['link']}\">{a['title']}</a> — {a['source']}")
    lines += ["", "این فهرست پایش خبر است؛ اثر هر خبر بر قیمت باید پس از بررسی متن و زمینه بازار ارزیابی شود.", "", footer()]
    return "\n".join(lines)

def footer():
    return '<b><a href="https://t.me/FundBoard_Silver">@FundBoard_Silver | فاندبورد نقره\n‎داشبورد</a></b> <b><a href="https://t.me/FundBoard_Silver">سرمایه‌گذاری شما</a></b>'

def macro_post():
    # Publish only sourced, factual context. Do not invent latest industrial-demand figures.
    return "\n".join([
        "🌐 <b>بررسی بنیادی نقره</b>", f"🕒 زمان گزارش: {stamp()}", "",
        "• <b>تقاضای صنعتی:</b> مصرف در صنایع خورشیدی، الکترونیک و برق از متغیرهای مهم تقاضای نقره است.",
        "• <b>عرضه:</b> بخش مهمی از تولید نقره به‌صورت محصول جانبی استخراج فلزاتی مانند سرب، روی، مس و طلا به دست می‌آید؛ بنابراین عرضه لزوماً سریع به قیمت نقره واکنش نشان نمی‌دهد.",
        "• <b>متغیرهای کلان:</b> دلار آمریکا، بازده واقعی اوراق، نرخ بهره و وضعیت فعالیت صنعتی می‌توانند بر قیمت اثر بگذارند.",
        "• <b>محدودیت داده:</b> در این نسخه رقم تازه عرضه/تقاضا یا پیش‌بینی عددی منتشر نمی‌شود مگر آنکه گزارش رسمی تاریخ‌دار دریافت و بررسی شود.",
        "", "منبع مرجع عرضه و تقاضا: <a href=\"https://silverinstitute.org/\">The Silver Institute</a>.", "", footer()
    ])

def periodic_post():
    return "\n".join([
        "📅 <b>گزارش دوره‌ای بازار نقره</b>", f"🕒 زمان تهیه: {stamp()}", "",
        "این بخش برای گزارش‌های هفتگی و ماهانه طراحی شده است: بازدهی نقره جهانی، مقایسه با طلا، نسبت طلا به نقره و خلاصه تغییرات عرضه و تقاضا.",
        "در این اجرای آزمایشی، ارقام بازدهی دوره‌ای منتشر نمی‌شوند تا زمانی که تاریخ‌های ابتدا/انتها و داده‌های تاریخی معتبر کنترل شوند.",
        "منبع مرجع گزارش‌های صنعتی: <a href=\"https://silverinstitute.org/\">The Silver Institute</a>.", "", footer()
    ])

def specialist_posts():
    topics = [
        ("آموزش نقره", "نقره فیزیکی یا صندوق نقره؟", "در مقایسه این دو روش، فقط بازدهی را نبینید. اختلاف قیمت بازار با NAV، هزینه معامله، نقدشوندگی، هزینه نگهداری و امکان تحویل فیزیکی نیز مهم‌اند. هیچ روشی در همه شرایط برنده نیست.", "شما کدام روش را ترجیح می‌دهید؟"),
        ("عوامل بنیادی", "چرا صنعت خورشیدی برای نقره مهم است؟", "نقره به دلیل رسانایی الکتریکی در فناوری‌های خورشیدی کاربرد دارد. بااین‌حال، تقاضای صنعتی تنها عامل قیمت نیست؛ عرضه معادن، بازیافت، نرخ ارز و جریان سرمایه‌گذاری هم اثر دارند.", "فکر می‌کنید رشد انرژی خورشیدی چه اثری بر بازار نقره دارد؟"),
        ("ریسک سرمایه‌گذاری", "چرا نقره می‌تواند از طلا پرنوسان‌تر باشد؟", "نقره هم دارایی سرمایه‌گذاری و هم فلزی صنعتی است. در نتیجه، تغییر انتظارات اقتصادی می‌تواند هم‌زمان تقاضای صنعتی و تقاضای سرمایه‌گذاری را تغییر دهد. نوسان بیشتر به معنی بازدهی تضمین‌شده بیشتر نیست.", "در انتخاب فلزات گران‌بها، نوسان را چقدر مهم می‌دانید؟"),
        ("تحلیل نسبی", "نسبت طلا به نقره چه می‌گوید؟", "این نسبت نشان می‌دهد قیمت یک اونس طلا چند برابر قیمت یک اونس نقره است. نسبت بالا یا پایین می‌تواند برای مقایسه عملکرد نسبی مفید باشد، اما به‌تنهایی سیگنال قطعی خریدوفروش نیست.", "آیا نسبت طلا به نقره را دنبال می‌کنید؟"),
    ]
    posts = []
    for cat, title, body, question in topics:
        posts.append("\n".join([f"📚 <b>{cat} | {title}</b>", "", body, "", question, "", footer()]))
    return posts

def fund_diagnostic():
    # Intentionally does not fabricate Iranian silver fund NAV, prices or returns.
    return {
        "status": "not_published",
        "reason": "Iranian silver-fund market data must be mapped to a verified official or trusted data source before publishing numbers.",
        "planned_fields": ["symbol", "market_price", "nav", "premium_discount_pct", "daily_return", "weekly_return", "monthly_return", "volume", "value", "aum", "holdings", "source_timestamp"],
        "validation": "Never infer NAV, returns, flows or AUM from missing values; suppress stale/incomplete records."
    }

def main():
    OUTPUT.mkdir(exist_ok=True)
    now = datetime.now(TEHRAN).isoformat()
    results = {"generated_at_tehran": now, "mode": "dry_run_no_telegram", "content_families": []}
    checks = []
    # Real data-backed modules; any fetch failure is reported explicitly.
    for name, func in [("technical", technical_post), ("macro_education", macro_post), ("periodic_context", periodic_post)]:
        try:
            content = func()
            (OUTPUT / f"{name}.html").write_text(content + "\n", encoding="utf-8")
            results["content_families"].append({"name":name,"status":"generated","characters":len(content)})
            checks.append(True)
            print(f"[OK] {name}: generated {len(content)} characters")
        except Exception as exc:
            results["content_families"].append({"name":name,"status":"failed","error":str(exc)})
            checks.append(False)
            print(f"[FAIL] {name}: {exc}")
    try:
        articles = fetch_news()
        content = news_post(articles)
        (OUTPUT / "news_monitor.html").write_text(content + "\n", encoding="utf-8")
        (OUTPUT / "news_items.json").write_text(json.dumps(articles,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        results["content_families"].append({"name":"news_monitor","status":"generated","articles":len(articles),"characters":len(content)})
        checks.append(True)
        print(f"[OK] news_monitor: {len(articles)} fresh dated items")
    except Exception as exc:
        results["content_families"].append({"name":"news_monitor","status":"failed","error":str(exc)})
        checks.append(False)
        print(f"[FAIL] news_monitor: {exc}")
    posts = specialist_posts()
    (OUTPUT / "specialist_educational_posts.json").write_text(json.dumps(posts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUTPUT / "iran_silver_funds_diagnostic.json").write_text(json.dumps(fund_diagnostic(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    results["content_families"] += [
        {"name":"specialist_educational_posts","status":"generated","count":len(posts)},
        {"name":"iran_silver_funds","status":"blocked_pending_verified_data_source","count":0}
    ]
    results["checks_passed"] = sum(checks)
    results["checks_total"] = len(checks)
    results["telegram_messages_sent"] = 0
    (OUTPUT / "suite_report.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(results,ensure_ascii=False,indent=2))
    # fail workflow only for core live data checks; no post is ever sent.
    if not all(checks):
        sys.exit(1)

if __name__ == "__main__":
    main()
