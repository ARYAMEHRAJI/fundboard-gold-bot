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
 OUT.parent.mkdir(parents=True,exist_ok=True)
 now=datetime.now(ZoneInfo("Asia/Tehran"))
 lines=["🌍 داده‌های بنیادی و اقتصاد کلان مؤثر بر نقره",f"تاریخ گزارش تهران: {now:%Y/%m/%d}",""]
 ok=0
 for sid,label in SERIES.items():
  try:
   d,v,age=latest(get(FRED.format(sid)))
   lines.append(f"• **{label}:** {v:.3f} درصد؛ تاریخ مشاهده {d}")
   ok+=1
  except Exception:
   # Omit missing or stale series; do not publish exception strings.
   continue
 lines += ["","📰 خبرهای تازه درباره عرضه و تقاضای نقره"]
 items=[]
 try:
  root=ET.fromstring(get(RSS)); items=[]; seen=set()
  for item in root.findall(".//item"):
   title=(item.findtext("title") or "").strip()
   raw=(item.findtext("pubDate") or "").strip()
   summary=ET.tostring(item,encoding="unicode",method="xml")
   try:
    dt=parsedate_to_datetime(raw)
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    age=(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/86400
   except Exception: continue
   normalized=title.casefold()
   if not title or not (-1<=age<=30) or normalized in seen: continue
   if not any(term in (title+" "+summary).casefold() for term in ("silver","solar","mine","mining","supply","demand","production")): continue
   if any(term in (title+" "+summary).casefold() for term in ("india silver rate","vietnam silver price","bundi silver","kolkata silver","delhi silver","mumbai silver")): continue
   seen.add(normalized); items.append((dt,title))
  for dt,title in sorted(items,reverse=True)[:4]:
   lines.append(f"• تاریخ {dt:%Y-%m-%d}: {title}")
 except Exception:
  pass
 if ok==0 and not items:
  raise SystemExit("داده بنیادی معتبر یا خبر مرتبط دریافت نشد؛ انتشار متوقف شد.")
 report="\n".join(lines).strip()
 OUT.write_text(report,encoding="utf-8")
 print(report)
 print(f"MACRO_SERIES_OK: {ok}/{len(SERIES)}")
 print("TELEGRAM_MESSAGES_SENT: 0")

if __name__=="__main__":main()
