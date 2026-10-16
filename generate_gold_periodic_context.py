"""Fetch dated World Gold Council gold ETF and central-bank context, dry-run only.

This monitor extracts dated source metadata and short text snippets. It does not
claim that periodic data are daily, and it does not send Telegram messages.
"""
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

ETF_PAGE = "https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows"
RESERVES_PAGE = "https://www.gold.org/goldhub/data/gold-reserves-by-country"
BASE = "https://www.gold.org"
TIMEOUT = 25
MAX_PAGE_AGE_DAYS = 100


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.text = []
        self.links = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "a" and attrs.get("href"):
            self.links.append((attrs["href"], ""))
        if tag in {"p", "h1", "h2", "h3", "li"}:
            self.text.append("\\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value or self._skip_depth:
            return
        if self._in_title:
            self.title.append(value)
        self.text.append(value)
        if self.links:
            href, label = self.links[-1]
            if not label:
                self.links[-1] = (href, value)


def fetch_page(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "FundBoardGoldBot/1.0 (research draft)"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        final_url = response.geturl()
        if urlparse(final_url).scheme != "https" or urlparse(final_url).hostname not in {
            "www.gold.org", "gold.org"
        }:
            raise ValueError("Unexpected final URL for World Gold Council source")
        html = response.read().decode("utf-8", errors="replace")
    parser = PageParser()
    parser.feed(html)
    return {
        "url": final_url,
        "title": " ".join(parser.title).strip() or final_url,
        "text": re.sub(r"\\s+", " ", " ".join(parser.text)).strip(),
        "links": [(urljoin(final_url, href), label) for href, label in parser.links],
    }


def extract_dates(text):
    found = []
    patterns = [
        r"\\b(?:[0-3]?\\d\\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+20\\d{2}\\b",
        r"\\b20\\d{2}-\\d{2}-\\d{2}\\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            raw = match.group(0)
            for fmt in ("%d %B %Y", "%B %Y", "%Y-%m-%d"):
                try:
                    value = datetime.strptime(raw, fmt).date()
                    found.append((value, raw))
                    break
                except ValueError:
                    continue
    return sorted(set(found))


def find_latest_etf_article(page):
    candidates = []
    for url, label in page["links"]:
        path = urlparse(url).path.rstrip("/")
        match = re.search(r"/goldhub/research/gold-etfs-(?:holdings-and-flows|holdings-flows)/(20\\d{2})/(0?[1-9]|1[0-2])$", path)
        if match and urlparse(url).hostname in {"www.gold.org", "gold.org"}:
            candidates.append((int(match.group(1)), int(match.group(2)), url))
    if not candidates:
        return None
    _, _, url = max(candidates)
    article = fetch_page(url)
    dates = extract_dates(article["text"])
    article["date"] = max((d.isoformat() for d, _ in dates), default="not identified")
    article["url"] = url
    # Short, source-attributed excerpts only; no inferred numeric values.
    article["excerpt"] = article["text"][:1100]
    return article


def build_report(etf_page, reserves_page, etf_article=None, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc)
    today = generated_at.date()
    lines = [
        "🟡 فاندبورد طلا | پایش داده‌های دوره‌ای شورای جهانی طلا",
        f"زمان ساخت (UTC): {generated_at.isoformat()}",
        "",
        "این بخش مکمل گزارش تکنیکال و کلان است؛ داده‌های دوره‌ای را نباید داده روزانه تلقی کرد.",
        "",
        "📊 ETFهای طلای جهانی",
        f"صفحه رسمی: {etf_page['url']}",
        f"عنوان صفحه: {etf_page['title']}",
        "بسامد اعلام‌شده توسط منبع: هفتگی/ماهانه؛ فایل‌های دانلودی اصلی معمولاً ماهانه هستند.",
    ]
    if etf_article:
        lines.extend([
            f"آخرین مقاله ماهانه قابل شناسایی از لینک‌های صفحه: {etf_article['title']}",
            f"لینک مقاله: {etf_article['url']}",
            f"تاریخ استخراج‌شده از متن صفحه (نیازمند بررسی): {etf_article['date']}",
            "خلاصه متن صفحه (برای جلوگیری از تحریف، به‌جای استخراج خودکار ارقام):",
            etf_article["excerpt"],
        ])
    else:
        lines.append("مقاله ماهانه قابل شناسایی نبود؛ جهت جریان و ارقام گزارش نمی‌شود.")
    lines.extend([
        "",
        "🏦 ذخایر طلای بانک‌های مرکزی",
        f"صفحه رسمی: {reserves_page['url']}",
        f"عنوان صفحه: {reserves_page['title']}",
        "این منبع داده‌های ماهانه و فصلی را منتشر می‌کند و داده‌ها ممکن است با تأخیر گزارش شوند.",
    ])
    dates = extract_dates(reserves_page["text"])
    if dates:
        lines.append("تاریخ‌های دیده‌شده در صفحه (صرفاً سرنخ متنی، نه تضمین تاریخ آخرین داده): " +
                     ", ".join(raw for _, raw in dates[-4:]))
    else:
        lines.append("تاریخ آخرین مشاهده/به‌روزرسانی از متن صفحه به‌طور مطمئن استخراج نشد.")
    lines.extend([
        "تا وقتی فایل داده رسمی دریافت و ستون‌های تاریخ/مقدار اعتبارسنجی نشده‌اند، تغییر خرید بانک‌های مرکزی محاسبه یا حدس زده نمی‌شود.",
        "",
        "محدودیت: این نسخه پایشگر صفحه و متن رسمی است، نه جایگزین فایل‌های داده XLSX یا روش‌شناسی شورای جهانی طلا.",
        "⚠️ محتوای آموزشی و اطلاعاتی؛ نه توصیه خرید یا فروش.",
        "Dry-run only: no Telegram message was sent.",
    ])
    return "\\n".join(lines)


def main():
    warnings = []
    try:
        etf_page = fetch_page(ETF_PAGE)
    except Exception as exc:
        warnings.append(f"ETF page unavailable: {type(exc).__name__}: {exc}")
        etf_page = {"url": ETF_PAGE, "title": "Unavailable", "text": "", "links": []}
    try:
        reserves_page = fetch_page(RESERVES_PAGE)
    except Exception as exc:
        warnings.append(f"Reserves page unavailable: {type(exc).__name__}: {exc}")
        reserves_page = {"url": RESERVES_PAGE, "title": "Unavailable", "text": "", "links": []}
    article = None
    if etf_page["text"]:
        try:
            article = find_latest_etf_article(etf_page)
        except Exception as exc:
            warnings.append(f"ETF article unavailable: {type(exc).__name__}: {exc}")
    for warning in warnings:
        print("WARNING:", warning)
    report = build_report(etf_page, reserves_page, article)
    with open("gold_periodic_context_draft.txt", "w", encoding="utf-8") as output:
        output.write(report + "\\n")
    print(report)


if __name__ == "__main__":
    main()
