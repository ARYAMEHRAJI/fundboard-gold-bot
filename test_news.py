
import json
import urllib.parse
import urllib.request

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

params = {
    "query": "(gold OR bullion)",
    "mode": "ArtList",
    "format": "json",
    "maxrecords": "10",
    "sort": "DateDesc",
}

url = API_URL + "?" + urllib.parse.urlencode(params)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "FundBoardGoldBot/1.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    data = json.loads(response.read().decode("utf-8"))

articles = data.get("articles", [])

if not articles:
    raise RuntimeError("No news articles returned")

print("=== FUND BOARD GOLD NEWS TEST ===")
print("Articles found:", len(articles))

for i, article in enumerate(articles[:10], start=1):
    print(f"\n[{i}] {article.get('title', 'No title')}")
    print("Source:", article.get("domain", "Unknown"))
    print("Date:", article.get("seendate", "Unknown"))
    print("URL:", article.get("url", ""))
    print("Language:", article.get("language", "Unknown"))
  
