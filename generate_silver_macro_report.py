"""Silver macro report based on dated FRED observations and Silver Institute news RSS. Dry-run only."""
import csv, io, json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, date
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT=Path("silver_content_preview/macro_report.html")
TIMEOUT=25
FRED="https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
RSS="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":'"Silver Institute" OR "silver supply" OR "silver demand" OR "solar silver" when:30d',"hl":"en-US","gl":"US","ceid":"US:en"})
SERIES={"DFII10":"بازده واقعی اوراق ۱۰ساله آمریکا","DTWEXBGS":"شاخص گسترده دلار آمریکا (نه DXY)","DFF":"نرخ مؤثر وجوه فدرال"}
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"FundBoardSilver/1.0 research"})
 with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return r.read().decode("utf-8",errors="replace")
def latest(text):
 rows=list(csv.DictReader(io.StringIO(text))); vals=[]
 for row in rows:
  try:
   d=date.fromisoformat(row["observation_date"]); k=next(k for k in row if k!="observation_date"); v=float(row[k])
   vals.append((d,v))
  except Exception: pass
 if not vals: raise ValueError("no numeric FRED observations")
 d,v=max(vals)
 age=(datetime.now(timezone.utc).date()-d).days
 if age<0 or age>10: raise ValueError(f"stale or future FRED observation ({age} days)")
 return d.isoformat(),v,age
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True); now=datetime.now(ZoneInfo("Asia/Tehran"))
 lines=["🌐 فاندبورد نقره | عوامل کلان و بنیادی بازار",f"زمان گزارش تهران: {now:%Y-%m-%d %H:%M}","",
 "📌 داده‌های اقتصاد کلان (منبع FRED؛ هر مشاهده تاریخ مستقل دارد)"]
 ok=0
 for sid,label in SERIES.items():
  try:
   d,v,age=latest(get(FRED.format(sid))); lines.append(f"• {label}: {v:.3f}؛ تاریخ داده {d} (قدمت {age} روز)");ok+=1
  except Exception as e: lines.append(f"• {label}: داده معتبر در دسترس نیست ({type(e).__name__})")
 lines += ["","🧭 چارچوب تفسیر","• دلار قوی‌تر و افزایش نرخ‌های واقعی می‌تواند هزینه فرصت نگهداری فلزات بدون بازده را بالا ببرد؛ رابطه قطعی و همیشگی نیست.",
 "• برای نقره، تقاضای صنعتی و عرضه معادن/بازیافت در کنار عوامل مالی مهم‌اند؛ خبر یک صنعت به‌تنهایی جهت قیمت را تعیین نمی‌کند.","",
 "📰 اخبار مرتبط با عرضه و تقاضا (تا ۳۰ روز اخیر)"]
 try:
  root=ET.fromstring(get(RSS)); items=[]; seen=set()
  for item in root.findall(".//item"):
   title=(item.findtext("title") or "").strip(); link=(item.findtext("link") or "").strip(); raw=(item.findtext("pubDate") or "").strip()
   try:
    dt=parsedate_to_datetime(raw)
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    age=(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/86400
   except Exception:continue
   if title and link.startswith("https://") and -1<=age<=30 and title.casefold() not in seen:
    seen.add(title.casefold());items.append((dt,title,link))
  for dt,title,link in sorted(items,reverse=True)[:6]: lines.append(f"• {dt:%Y-%m-%d}: {title} — {link}")
  if not items:lines.append("خبر واجد شرایطی پیدا نشد؛ این به معنی نبود خبر مرتبط نیست.")
 except Exception as e:lines.append(f"دریافت خبر ناموفق بود: {type(e).__name__}")
 lines += ["","منابع: FRED series "+", ".join(SERIES)+ "؛ Google News RSS برای کشف خبر (نه منبع آمار قطعی).",
 "اطلاعات ذخایر و جریان ETFها فقط با انتشار رسمی و تاریخ‌دار قابل گزارش است؛ در نبود آن عددی تخمین زده نمی‌شود.",
 "این گزارش زمینه تحلیلی است و سیگنال قطعی خریدوفروش نیست.","Dry-run only: no Telegram message was sent."]
 report="\n".join(lines);OUT.write_text(report,encoding="utf-8");print(report);print(f"FRED_SERIES_OK: {ok}/{len(SERIES)}");print("TELEGRAM_MESSAGES_SENT: 0")
if __name__=="__main__":main()
