
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

params = {
    "query": '"gold price" OR "spot gold" OR "gold bullion"',
    "mode": "ArtList",
    "format": "json",
    "maxrecords": "5",
    "sort": "DateDesc",
    "timespan": "24h",
    "sourcelang": "English",
}

url = API_URL + "?" + urllib.parse.urlencode(params)
request = urllib.request.Request(
    url,
    headers={"User-Agent": "FundBoardGoldBot/1.0"}
)

for attempt in range(2):
    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            data = json.loads(response.read().decode("utf-8"))

        articles = data.get("articles", [])
        print("=== FUND BOARD GOLD NEWS TEST ===")
        print("Articles found:", len(articles))

        for i, article in enumerate(articles, start=1):
            print(f"\n[{i}] {article.get('title', 'No title')}")
            print("Source:", article.get("domain", "Unknown"))
            print("Date:", article.get("seendate", "Unknown"))
            print("URL:", article.get("url", ""))

        break

    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            print("GDELT rate limit reached (HTTP 429).")
            print("Wait before trying again; no repeated requests.")
            break
        raise
        
