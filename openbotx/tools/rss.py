import json
import re
from typing import Any
from xml.etree.ElementTree import Element, fromstring

import httpx

from openbotx.tools.base import Tool

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _strip_tags(text: str) -> str:
    """Remove HTML tags from text."""
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _text(el: Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _text_ns(el: Element, tag: str) -> str:
    child = el.find(f"atom:{tag}", ATOM_NS) or el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_rss(root: Element) -> list[dict[str, str]]:
    """Parse RSS 2.0 feed (channel/item)."""
    items = root.findall(".//channel/item")
    if not items:
        return []
    entries = []
    for item in items:
        summary = _text(item, "description")
        entries.append(
            {
                "title": _text(item, "title"),
                "link": _text(item, "link"),
                "published": _text(item, "pubDate"),
                "summary": _strip_tags(summary)[:500] if summary else "",
            }
        )
    return entries


def _parse_atom(root: Element) -> list[dict[str, str]]:
    """Parse Atom feed (atom:entry)."""
    items = root.findall("atom:entry", ATOM_NS) or root.findall("entry")
    if not items:
        return []
    entries = []
    for item in items:
        link_el = item.find("atom:link", ATOM_NS) or item.find("link")
        link = ""
        if link_el is not None:
            link = link_el.get("href", "") or (link_el.text or "")

        published = _text_ns(item, "published") or _text_ns(item, "updated")
        summary = _text_ns(item, "summary") or _text_ns(item, "content")

        entries.append(
            {
                "title": _text_ns(item, "title"),
                "link": link.strip(),
                "published": published,
                "summary": _strip_tags(summary)[:500] if summary else "",
            }
        )
    return entries


class RssReaderTool(Tool):
    """Read RSS and Atom feeds."""

    name = "rss_reader"
    description = (
        "Read an RSS or Atom feed and return the latest entries. "
        "Returns title, link, published date, and summary for each entry."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "RSS/Atom feed URL"},
            "count": {
                "type": "integer",
                "description": "Max entries to return (default 10)",
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["url"],
    }

    async def execute(self, url: str, count: int = 10, **kwargs: Any) -> str:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                r = await client.get(url, headers={"User-Agent": "OpenBotX/1.0 RSS Reader"})
                r.raise_for_status()

            root = fromstring(r.text)
            entries = _parse_rss(root) or _parse_atom(root)

            if not entries:
                return json.dumps(
                    {"error": "No entries found or unsupported feed format", "url": url},
                    ensure_ascii=False,
                )

            return json.dumps(
                {"url": url, "count": len(entries[:count]), "entries": entries[:count]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)
