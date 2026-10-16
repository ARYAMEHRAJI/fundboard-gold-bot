"""Diagnose the public Fundbase silver-funds page; does not invent fund metrics or publish."""
import json
import re
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://app.fundbase.ir/categories/%D9%86%D9%82%D8%B1%D9%87"
OUT = Path("silver_content_preview/iran_silver_funds_diagnostic.json")
TEHRAN = ZoneInfo("Asia/Tehran")


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_on = False
        self.title = []
        self.scripts = []
        self.links = []
        self.text = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title": self.title_on = True
        if tag in {"script","style","noscript","svg"}: self.skip += 1
        if tag == "script" and a.get("src"): self.scripts.append(a["src"])
        if tag in {"a","link"} and a.get("href"): self.links.append(a["href"])
    def handle_endtag(self, tag):
        if tag == "title": self.title_on = False
        if tag in {"script","style","noscript","svg"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if self.title_on: self.title.append(data)
        if not self.skip and data.strip(): self.text.append(" ".join(data.split()))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent":"Mozilla/5.0 FundBoardSilver/1.0","Accept-Language":"fa-IR,fa;q=0.9,en;q=0.8"})
    result = {"checked_at_tehran":datetime.now(TEHRAN).isoformat(),"source_url":URL,"status":"unknown",
              "metrics_published":False,"warning":"No price/NAV/return/AUM/flow is reported unless an identifiable, current data feed is validated."}
    try:
        with urllib.request.urlopen(req,timeout=40) as response:
            raw=response.read()
            result.update({"status":"ok","http_status":response.status,"final_url":response.geturl(),
                           "content_type":response.headers.get("Content-Type",""),"html_bytes":len(raw)})
        page=raw.decode("utf-8",errors="replace")
        p=Parser(); p.feed(page)
        urls=sorted(set(re.findall(r"""https?://[^"'\s<>]+""",page)))
        api_refs=sorted(set(re.findall(r"""[^"'\s<>]*(?:/api/|graphql|trpc|investats)[^"'\s<>]*""",page,re.I)))
        result.update({"title":" ".join(p.title).strip(),"script_sources":p.scripts[:80],
                       "linked_assets":p.links[:100],"external_urls":urls[:120],"api_like_references":api_refs[:120],
                       "visible_text_excerpt":" ".join(p.text)[:2500],
                       "metrics_published":False,
                       "next_step":"Inspect the detected public API/feed and validate fields and timestamps before calculating fund metrics."})
    except Exception as exc:
        result.update({"status":"failed","error":f"{type(exc).__name__}: {exc}",
                       "next_step":"Retry later or inspect the official public source manually; do not substitute guessed data."})
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print("TELEGRAM_MESSAGES_SENT: 0")


if __name__ == "__main__":
    main()
