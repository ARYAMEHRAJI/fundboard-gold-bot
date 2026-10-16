
import json
import re
import traceback
import urllib.request
import urllib.error

from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_URL = "https://app.fundbase.ir/categories/%D8%B7%D9%84%D8%A7"

OUTPUT_HTML = Path("fundbase_gold_page.html")
OUTPUT_JSON = Path("fundbase_page_diagnostic.json")
OUTPUT_REPORT = Path("fundbase_page_diagnostic.txt")
OUTPUT_ERROR = Path("fundbase_error.txt")

TEHRAN = ZoneInfo("Asia/Tehran")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.title_text = []
        self.scripts = []
        self.links = []
        self.current_script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "title":
            self.title = True

        elif tag == "script":
            src = attrs.get("src")
            if src:
                self.scripts.append(src)

        elif tag == "link":
            href = attrs.get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag == "title":
            self.title = False

    def handle_data(self, data):
        if self.title:
            self.title_text.append(data)


def log(message):
    print(message, flush=True)


def fetch_page():
    request = urllib.request.Request(
        BASE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    )

    log(f"REQUEST_URL: {BASE_URL}")

    with urllib.request.urlopen(request, timeout=40) as response:
        status = response.status
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
        raw = response.read()

    html = raw.decode("utf-8", errors="replace")

    log(f"HTTP_STATUS: {status}")
    log(f"FINAL_URL: {final_url}")
    log(f"CONTENT_TYPE: {content_type}")
    log(f"HTML_BYTES: {len(raw)}")

    return html, status, final_url, content_type


def main():
    now = datetime.now(TEHRAN)

    log("MODE: DRY_RUN")
    log(f"TIME_TEHRAN: {now.isoformat()}")

    html, status, final_url, content_type = fetch_page()

    OUTPUT_HTML.write_text(html, encoding="utf-8")

    parser = PageParser()
    parser.feed(html)

    # Extract URLs and likely API references from the page source.
    urls = sorted(set(re.findall(
        r"""https?://[^"'\\\s<>]+""",
        html
    )))

    api_references = sorted(set(re.findall(
        r"""[^"'\\\s<>]*(?:/api/|graphql|trpc|investats)[^"'\\\s<>]*""",
        html,
        flags=re.IGNORECASE
    )))

    # Check whether the initial HTML contains visible gold-fund data.
    keywords = (
        "صندوق‌های طلا",
        "ارزش معاملات",
        "ورود نقدینگی",
        "حباب",
        "NAV",
        "بازدهی",
    )

    keyword_counts = {
        keyword: html.count(keyword)
        for keyword in keywords
    }

    result = {
        "mode": "dry_run",
        "checked_at_tehran": now.isoformat(),
        "requested_url": BASE_URL,
        "final_url": final_url,
        "http_status": status,
        "content_type": content_type,
        "html_bytes": len(html.encode("utf-8")),
        "page_title": "".join(parser.title_text).strip(),
        "script_count": len(parser.scripts),
        "scripts": parser.scripts,
        "links_count": len(parser.links),
        "links": parser.links[:100],
        "external_urls": urls[:200],
        "possible_api_references": api_references[:200],
        "keyword_counts_in_html": keyword_counts,
        "html_preview": html[:3000],
        "warning": (
            "This is a page-source diagnostic, not a verified market-data "
            "feed. URLs found in HTML are candidates only. No market values "
            "are calculated and no Telegram messages are sent."
        ),
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = [
        "FUNDBOARD GOLD — PAGE CONNECTION DIAGNOSTIC",
        f"Checked at: {now.isoformat()}",
        f"Requested URL: {BASE_URL}",
        f"Final URL: {final_url}",
        f"HTTP status: {status}",
        f"Content type: {content_type}",
        f"HTML bytes: {len(html.encode('utf-8'))}",
        f"Page title: {result['page_title']}",
        f"JavaScript files: {len(parser.scripts)}",
        f"Links found: {len(parser.links)}",
        "",
        "KEYWORD COUNTS IN INITIAL HTML:",
    ]

    for keyword, count in keyword_counts.items():
        report.append(f"{keyword}: {count}")

    report.extend([
        "",
        "POSSIBLE API REFERENCES:",
        *api_references[:100],
        "",
        "JAVASCRIPT FILES:",
        *parser.scripts[:100],
        "",
        "EXTERNAL URLS:",
        *urls[:100],
        "",
        "HTML PREVIEW:",
        html[:3000],
        "",
        "No Telegram messages were sent.",
    ])

    OUTPUT_REPORT.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    log(f"JSON_OUTPUT: {OUTPUT_JSON}")
    log(f"REPORT_OUTPUT: {OUTPUT_REPORT}")
    log(f"HTML_OUTPUT: {OUTPUT_HTML}")
    log("RESULT: SUCCESS")
    log("No Telegram messages were sent.")


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        details = (
            f"FAILED: {type(exc).__name__}: {exc}\n\n"
            f"{traceback.format_exc()}"
        )

        log(details)

        try:
            OUTPUT_ERROR.write_text(details, encoding="utf-8")
            log(f"ERROR_FILE: {OUTPUT_ERROR}")
        except Exception as save_exc:
            log(f"ERROR_SAVE_FAILED: {save_exc}")

        raise
