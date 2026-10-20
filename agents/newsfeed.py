"""News agent: Indian business news and global/domestic macro news from public RSS feeds.

Polled every few minutes. Each headline is linked to our stocks (company names), sectors,
the Indian market or global events, given a tone and an importance, and written to the
intelligence log for the Data Analyzer.
"""
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import requests

from . import intel

IST = ZoneInfo("Asia/Kolkata")
_G = "https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q="
FEEDS = {
    "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Mint": "https://www.livemint.com/rss/markets",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    "CNBC-TV18": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/market.xml",
    "Google: India markets": _G + "Nifty+OR+Sensex+OR+%22Indian+stocks%22+when:1d",
    "Google: global macro": _G + "crude+OR+OPEC+OR+%22Federal+Reserve%22+OR+sanctions+OR+tariffs+OR+war+when:1d",
    "Google: India macro": _G + "RBI+OR+rupee+OR+FII+OR+%22India+inflation%22+OR+SEBI+when:1d",
    "Google: commodities": _G + "%22aluminium+prices%22+OR+%22copper+prices%22+OR+%22steel+prices%22+OR+%22gold+prices%22+when:1d",
}


def _when(text: str) -> str:
    try:
        return parsedate_to_datetime(text).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def parse(xml_text: str, source: str) -> list[dict]:
    items = []
    for node in ET.fromstring(xml_text).iter("item"):
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        link = (node.findtext("link") or "").strip()
        uid = hashlib.sha1(title.lower().encode()).hexdigest()[:16]  # same story from two feeds counts once
        items.append(intel.make_item(id=f"news-{uid}", time=_when(node.findtext("pubDate")),
                                     source=source, kind="news", headline=title, url=link))
    return items


def fetch_all(timeout: int = 15) -> tuple[list[dict], list[str]]:
    items, failed = [], []
    for source, url in FEEDS.items():
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            resp.raise_for_status()
            items += parse(resp.text, source)
        except Exception:
            failed.append(source)
    return items, failed
