"""Fetch headlines about Jensen Huang and write news.json.

Standard library only. The GitHub Action runs this file on a schedule.
Only outlets in ALLOWED are kept, so gossip sites do not reach the page.
"""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEED = ("https://news.google.com/rss/search?"
        "q=%22Jensen+Huang%22+Nvidia+when:14d&hl=en-US&gl=US&ceid=US:en")

ALLOWED = {
    "reuters", "associated press", "ap news", "bloomberg", "bloomberg.com",
    "cnbc", "the wall street journal", "wsj", "the new york times",
    "financial times", "the verge", "bbc", "npr", "the washington post",
    "axios", "fortune", "sec.gov", "nvidia newsroom",
}


def parse(xml_text):
    items = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        source = (item.findtext("source") or "").strip()
        if source.lower() not in ALLOWED:
            continue
        link = (item.findtext("link") or "").strip()
        if not link.startswith(("http://", "https://")):
            continue
        title = (item.findtext("title") or "").strip()
        # Google News adds " - Outlet" to the end of each title
        suffix = " - " + source
        if title.endswith(suffix):
            title = title[: -len(suffix)]
        try:
            published = parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc).isoformat()
        except Exception:
            published = ""
        items.append({"title": title, "link": link, "source": source, "published": published})
    items.sort(key=lambda i: i["published"], reverse=True)
    return items[:25]


def main(out_path="news.json"):
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (tracker bot)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = parse(resp.read())
    if not items:
        print("No allowed headlines found; news.json not changed.")
        return
    data = {"updated": datetime.now(timezone.utc).isoformat(), "items": items}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(items)} headlines.")


if __name__ == "__main__":
    main(*sys.argv[1:])
