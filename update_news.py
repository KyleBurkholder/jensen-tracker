"""Fetch headlines about Jensen Huang and write news.json.

Standard library only. The GitHub Action runs this file on a schedule.
Only outlets in ALLOWED are kept, so gossip sites do not reach the page.

Headlines about the same relationship go into one group, so the page
counts each relationship one time and not one time per headline.
"""
import json
import re
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

# A headline with one of these words goes in the "Other alleged items" list.
ALLEGED = re.compile(
    r"alleg|reportedly|accus|\bclaims?\b|rumou?r|sources? says?|said to|"
    r"according to|\bprobe\b|investigat|whistleblow|lawsuit|\bsues?\b",
    re.IGNORECASE,
)

# ---- Grouping rules ----
# "second affair", "3rd relationship", "third employee" and so on -> group 2, 3, ...
ORDINALS = {"second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5, "sixth": 6, "6th": 6}
ORDINAL_REL = re.compile(
    r"\b(" + "|".join(ORDINALS) + r")\b[^.;:]{0,40}?"
    r"\b(affair|relationship|employee|woman|executive|staffer|subordinate)",
    re.IGNORECASE,
)
# Group 2: the reported relationship with an Nvidia employee.
GROUP2 = re.compile(
    r"relationship with (a |an |another )?(nvidia )?(executive|employee|staffer|subordinate)"
    r"|reports to him",
    re.IGNORECASE,
)
# Group 1: the admitted affair and the alleged intelligence link.
GROUP1 = re.compile(
    r"\bspy\b|\bspies\b|spying|espionage|intelligence (effort|operation|service)|"
    r"alice huang|honey ?trap",
    re.IGNORECASE,
)

MAX_PER_GROUP = 20
MAX_ITEMS = 40


def group_of(title):
    """Return the relationship group number for a headline, or None."""
    m = ORDINAL_REL.search(title)
    if m:
        return ORDINALS[m.group(1).lower()]
    if GROUP2.search(title):
        return 2
    if GROUP1.search(title):
        return 1
    return None


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
        items.append({"title": title, "link": link, "source": source, "published": published,
                      "alleged": bool(ALLEGED.search(title)), "group": group_of(title)})
    items.sort(key=lambda i: i["published"], reverse=True)
    return items


def merge(new_items, old_groups):
    """Split items into grouped and ungrouped. Keep old group entries so a
    relationship stays on the page after its headlines leave the feed."""
    groups = {str(k): list(v) for k, v in (old_groups or {}).items()}
    rest = []
    for it in new_items:
        g = it.pop("group")
        if g is None:
            rest.append(it)
            continue
        bucket = groups.setdefault(str(g), [])
        key = (it["title"].lower(), it["source"].lower())
        if not any((b["title"].lower(), b["source"].lower()) == key for b in bucket):
            bucket.append(it)
    for bucket in groups.values():
        bucket.sort(key=lambda i: i["published"], reverse=True)
        del bucket[MAX_PER_GROUP:]
    return rest[:MAX_ITEMS], groups


def main(out_path="news.json"):
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (tracker bot)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = parse(resp.read())
    if not items:
        print("No allowed headlines found; news.json not changed.")
        return
    try:
        with open(out_path, encoding="utf-8") as f:
            old_groups = json.load(f).get("groups", {})
    except Exception:
        old_groups = {}
    rest, groups = merge(items, old_groups)
    data = {"updated": datetime.now(timezone.utc).isoformat(), "groups": groups, "items": rest}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(rest)} headlines and {len(groups)} relationship groups.")


if __name__ == "__main__":
    main(*sys.argv[1:])
