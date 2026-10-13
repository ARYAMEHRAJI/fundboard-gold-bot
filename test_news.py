
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

query = '"gold price" OR "spot gold" OR "gold bullion" when:1d'

params = {
    "q": query,
    "hl": "en-US",
    "gl": "US",
    "ceid": "US:en",
}

url = (
    "https://news.google.com/rss/search?"
    + urllib.parse.urlencode(params)
)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "Mozilla/5.0 FundBoardGoldBot/1.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    xml_data = response.read()

root = ET.fromstring(xml_data)
items = root.findall("./channel/item")

print("=== FUND BOARD GOLD NEWS TEST ===")
print("Articles found:", len(items))

for i, item in enumerate(items[:10], start=1):
    title = item.findtext("title", default="No title")
    link = item.findtext("link", default="")
    pub_date = item.findtext("pubDate", default="Unknown")
    source = item.findtext("source", default="Unknown")

    print(f"\n[{i}] {title}")
    print("Source:", source)
    print("Date:", pub_date)
    print("URL:", link)

if not items:
    print("No matching news found.")
    
