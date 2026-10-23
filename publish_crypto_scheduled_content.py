#!/usr/bin/env python3
"""Generate and publish one data-grounded Persian post for FundBoard Crypto."""
import html
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

CHANNEL = os.getenv("TELEGRAM_CRYPTO_CHANNEL_ID", "@FundBoard_Crypto").strip()
TOKEN = os.getenv("TELEGRAM_CRYPTO_BOT_TOKEN", "").strip()
KIND = os.getenv("CONTENT_TYPE", "").strip().lower()
TEHRAN = ZoneInfo("Asia/Tehran")
TIMEOUT = 18
COINS = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple", "dogecoin"]
NAMES = {"bitcoin":"بیت‌کوین","ethereum":"اتریوم","solana":"سولانا","binancecoin":"بایننس‌کوین","ripple":"ریپل","dogecoin":"دوج‌کوین"}

def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent":"FundBoardCrypto/1.0"})
    r.raise_for_status()
    return r.json()

def market_data():
    data = get_json("https://api.coingecko.com/api/v3/coins/markets", {
        "vs_currency":"usd", "ids":",".join(COINS), "order":"market_cap_desc",
        "per_page":10, "page":1, "sparkline":"false", "price_change_percentage":"24h,7d"
    })
    if not data:
        raise RuntimeError("CoinGecko returned no market data")
    return {x["id"]:x for x in data}

def money(v):
    if v is None: return "ناموجود"
    if abs(v) >= 1000: return "$" + f"{v:,.0f}"
    if abs(v) >= 1: return "$" + f"{v:,.2f}"
    return "$" + f"{v:,.5f}"

def pct(v):
    return "ناموجود" if v is None else f"{v:+.2f}٪"

def stamp():
    return datetime.now(TEHRAN).strftime("%Y/%m/%d ـ %H:%M به وقت تهران")

def safe_text(s):
    return html.escape(str(s or "").strip(), quote=False)

def get_klines():
    rows = get_json("https://api.binance.com/api/v3/klines", {"symbol":"BTCUSDT","interval":"1d","limit":60})
    closes = [float(row[4]) for row in rows]
    if len(closes) < 50: raise RuntimeError("Not enough BTC daily candles")
    return closes

def rsi(closes, period=14):
    changes = [closes[i]-closes[i-1] for i in range(1,len(closes))]
    recent = changes[-period:]
    gains = sum(max(x,0) for x in recent)/period
    losses = sum(max(-x,0) for x in recent)/period
    if losses == 0: return 100.0 if gains else 50.0
    return 100-100/(1+gains/losses)

def build_prices(data):
    picks = [data[x] for x in ("bitcoin","ethereum","solana","ripple","dogecoin") if x in data]
    lines = ["<b>💹 نبض بازار رمزارزها</b>","","🕒 "+stamp(),""]
    for c in picks:
        lines.append(f"• {NAMES.get(c['id'],c['name'])}: <b>{money(c.get('current_price'))}</b> | ۲۴ساعت: {pct(c.get('price_change_percentage_24h'))}")
    lines += ["","این ارقام قیمت دلاری و تغییر ۲۴ساعته‌اند؛ برای تصمیم‌گیری، نقدشوندگی و نوسان هر دارایی را جداگانه بررسی کنید."]
    return "\n".join(lines)

def build_technical(data):
    closes = get_klines()
    last = closes[-1]
    r = rsi(closes)
    sma20 = sum(closes[-20:])/20
    sma50 = sum(closes[-50:])/50
    low20, high20 = min(closes[-20:]), max(closes[-20:])
    position = "بالاتر" if last > sma20 else "پایین‌تر"
    trend = "بالاتر" if sma20 > sma50 else "پایین‌تر"
    rsi_read = "در محدوده اشباع خرید" if r >= 70 else ("در محدوده اشباع فروش" if r <= 30 else "در محدوده میانی")
    return "\n".join(["<b>📈 بررسی تکنیکال بیت‌کوین</b>","", "🕒 "+stamp(),
        f"قیمت پایانی آخرین کندل روزانه: <b>{money(last)}</b>",
        f"RSI چهارده‌روزه: <b>{r:.1f}</b>؛ {rsi_read}.",
        f"میانگین ۲۰روزه: {money(sma20)}؛ قیمت فعلی {position} آن است.",
        f"میانگین ۲۰روزه نسبت به میانگین ۵۰روزه: {trend}.",
        f"بازه کمینه تا بیشینه ۲۰ کندل اخیر: {money(low20)} تا {money(high20)}.",
        "", "این سطوح از داده‌های کندل روزانه محاسبه شده‌اند و به‌تنهایی سیگنال خرید یا فروش نیستند."])

def build_news():
    feeds = ["https://www.coindesk.com/arc/outboundfeeds/rss/","https://cointelegraph.com/rss"]
    found = []
    for url in feeds:
        try:
            r = requests.get(url,timeout=TIMEOUT,headers={"User-Agent":"FundBoardCrypto/1.0"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = re.sub(r"\s+"," ",item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = re.sub(r"<[^>]+>"," ",item.findtext("description") or "")
                desc = re.sub(r"\s+"," ",html.unescape(desc)).strip()
                if title and link and len(title)>12: found.append((title,link,desc[:500]))
            if found: break
        except Exception as exc:
            print(f"RSS source unavailable: {url}: {exc}")
    if not found: raise RuntimeError("No usable crypto RSS headlines; refusing to publish invented news")
    lines = ["<b>🗞️ رصد اخبار بازار کریپتو</b>","","🕒 "+stamp(),""]
    for title,link,desc in found[:3]:
        lines.append(f"• <a href=\"{html.escape(link,quote=True)}\">{safe_text(title)}</a>")
        if desc: lines.append(safe_text(desc[:260])+("…" if len(desc)>260 else ""))
        lines.append("")
    lines.append("تیترها از خوراک خبری منتشرشده گردآوری شده‌اند؛ پیش از برداشت معاملاتی، متن اصلی و زمان انتشار خبر را بررسی کنید.")
    return "\n".join(lines)

def build_periodic(data):
    lines = ["<b>📊 کارنامه دوره‌ای رمزارزهای منتخب</b>","","🕒 "+stamp(),""]
    for key in ("bitcoin","ethereum"):
        c = data.get(key)
        if c: lines.append(f"• {NAMES[key]}: تغییر ۲۴ساعته {pct(c.get('price_change_percentage_24h'))} | هفت‌روزه {pct(c.get('price_change_percentage_7d_in_currency'))}")
    lines += ["","بازده هفت‌روزه تصویر کوتاه‌مدت می‌دهد و برای ارزیابی روند کافی نیست؛ آن را در کنار حجم معاملات، نوسان و شرایط کلان بخوانید."]
    return "\n".join(lines)

def build_alts(data):
    btc = data.get("bitcoin")
    alts = [data[x] for x in ("ethereum","solana","binancecoin","ripple","dogecoin") if x in data]
    alts.sort(key=lambda x:x.get("price_change_percentage_24h") if x.get("price_change_percentage_24h") is not None else -999,reverse=True)
    lines = ["<b>🧭 وضعیت آلت‌کوین‌های منتخب</b>","","🕒 "+stamp(),""]
    if btc: lines += [f"بیت‌کوین در ۲۴ ساعت: {pct(btc.get('price_change_percentage_24h'))}",""]
    for c in alts: lines.append(f"• {NAMES[c['id']]}: {pct(c.get('price_change_percentage_24h'))} | حجم ۲۴ساعته: {money(c.get('total_volume'))}")
    lines += ["","رشد چند آلت‌کوین به‌تنهایی تأییدکننده شروع آلت‌سیزن نیست؛ گستردگی رشد، حجم معاملات و عملکرد نسبی در برابر بیت‌کوین نیز اهمیت دارد."]
    return "\n".join(lines)

def build_macro(data):
    lines = ["<b>🌐 بازار کریپتو در قاب اقتصاد کلان</b>","","🕒 "+stamp(),""]
    for key in ("bitcoin","ethereum"):
        c = data.get(key)
        if c: lines.append(f"{NAMES[key]}: {money(c.get('current_price'))} | تغییر روزانه {pct(c.get('price_change_percentage_24h'))}")
    lines += ["","برای تحلیل میان‌مدت، مسیر نرخ بهره و بازده اوراق آمریکا، شاخص دلار، نقدینگی و جریان سرمایه صندوق‌های ETF را کنار رفتار قیمت بررسی کنید.",
        "داده قیمت به‌تنهایی علت حرکت بازار را مشخص نمی‌کند؛ بدون داده مستقل، نسبت‌دادن تغییر امروز به یک خبر یا متغیر کلان قابل اتکا نیست."]
    return "\n".join(lines)

def build_education():
    return "\n".join(["<b>🎓 آموزش کریپتو | تفاوت قیمت، ارزش بازار و حجم معاملات</b>","",
        "قیمت هر واحد به‌تنهایی معیار مناسبی برای مقایسه دو رمزارز نیست. ارزش بازار از ضرب قیمت در عرضه در گردش به دست می‌آید و اندازه نسبی یک دارایی را بهتر نشان می‌دهد.",
        "حجم معاملات نیز میزان دادوستد در یک بازه زمانی است؛ حجم بالا می‌تواند نشان‌دهنده فعالیت بیشتر باشد، اما به‌تنهایی جهت آینده قیمت را پیش‌بینی نمی‌کند.",
        "در ارزیابی یک پروژه، عرضه در گردش و حداکثری، برنامه آزادسازی توکن‌ها، نقدشوندگی و تمرکز مالکیت را هم بررسی کنید.",
        "🧩 مثال: توکنی با قیمت پایین ممکن است ارزش بازار بسیار بزرگی داشته باشد اگر تعداد واحدهای آن زیاد باشد."])

def build_briefing(data):
    lines = ["<b>🧾 جمع‌بندی روزانه بازار کریپتو</b>","","🕒 "+stamp(),""]
    for key in ("bitcoin","ethereum","solana"):
        c = data.get(key)
        if c: lines.append(f"• {NAMES[key]}: {money(c.get('current_price'))} | ۲۴ساعت {pct(c.get('price_change_percentage_24h'))} | ۷روز {pct(c.get('price_change_percentage_7d_in_currency'))}")
    lines += ["","برای جمع‌بندی امروز، سه موضوع را کنار هم بسنجید: جهت و قدرت روند بیت‌کوین، میزان همراهی آلت‌کوین‌ها و تغییر حجم معاملات.",
        "این گزارش بر داده‌های بازار متکی است؛ خبر یا عامل بنیادی مشخصی بدون تأیید مستقل به‌عنوان علت حرکت قیمت معرفی نمی‌شود."]
    return "\n".join(lines)

def send(post):
    if not TOKEN: raise RuntimeError("Missing TELEGRAM_CRYPTO_BOT_TOKEN secret")
    response = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id":CHANNEL,"text":post,"parse_mode":"HTML","disable_web_page_preview":True},timeout=TIMEOUT)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"): raise RuntimeError(f"Telegram rejected post: {body}")
    print(f"Published content_type={KIND} message_id={body.get('result',{}).get('message_id')} channel={CHANNEL}")

def main():
    allowed = {"prices","technical","news","periodic","alts","macro","education","briefing"}
    if KIND not in allowed: raise RuntimeError("CONTENT_TYPE must be one of: "+", ".join(sorted(allowed)))
    if KIND == "education": post = build_education()
    elif KIND == "news": post = build_news()
    else:
        data = market_data()
        post = {"prices":build_prices,"technical":build_technical,"periodic":build_periodic,
                "alts":build_alts,"macro":build_macro,"briefing":build_briefing}[KIND](data)
    send(post)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("ERROR: "+str(exc),file=sys.stderr)
        raise
