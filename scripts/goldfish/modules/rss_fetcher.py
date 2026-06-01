"""RSS/Atom fetcher with standard-library fallback."""

from __future__ import annotations

import email.utils
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from .utils import fetch_url, make_manual_item, now, strip_html, truncate


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _child_text(element: ET.Element, names: List[str]) -> str:
    for child in list(element):
        if _local_name(child.tag) in names:
            text = "".join(child.itertext())
            if text:
                return strip_html(text)
    return ""


def _entry_link(element: ET.Element) -> str:
    for child in list(element):
        if _local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
            text = (child.text or "").strip()
            if text:
                return text
    return ""


def _normalize_published(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.isoformat()
    except Exception:
        return value.strip()


def _parse_with_feedparser(raw: str, source: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    try:
        import feedparser  # type: ignore
    except Exception:
        return []
    parsed = feedparser.parse(raw)
    items: List[Dict[str, Any]] = []
    for entry in parsed.entries[:limit]:
        summary = strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        items.append(
            {
                "title": strip_html(getattr(entry, "title", "")),
                "url": getattr(entry, "link", "") or source.get("url", ""),
                "source_name": source.get("name", ""),
                "source_category": source.get("category", ""),
                "source_priority": source.get("priority", 1),
                "published": _normalize_published(
                    getattr(entry, "published", "") or getattr(entry, "updated", "")
                ),
                "summary": truncate(summary, 800),
                "raw_content": summary,
                "fetched_at": now().isoformat(),
                "content_type": source.get("content_type", "news"),
            }
        )
    return [item for item in items if item.get("title")]


def _parse_with_stdlib(raw: str, source: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    root = ET.fromstring(raw)
    candidates = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
    items: List[Dict[str, Any]] = []
    for entry in candidates[:limit]:
        summary = _child_text(entry, ["summary", "description", "content", "encoded"])
        items.append(
            {
                "title": _child_text(entry, ["title"]),
                "url": _entry_link(entry) or source.get("url", ""),
                "source_name": source.get("name", ""),
                "source_category": source.get("category", ""),
                "source_priority": source.get("priority", 1),
                "published": _normalize_published(_child_text(entry, ["published", "updated", "pubDate"])),
                "summary": truncate(summary, 800),
                "raw_content": summary,
                "fetched_at": now().isoformat(),
                "content_type": source.get("content_type", "news"),
            }
        )
    return [item for item in items if item.get("title")]


def fetch_rss_source(
    source: Dict[str, Any],
    limit: int = 5,
    timeout: int = 10,
    allow_network: bool = True,
) -> List[Dict[str, Any]]:
    rss_url = source.get("rss_url") or ""
    if not rss_url:
        return [
            make_manual_item(
                f"{source.get('name', 'Unknown source')}：待人工查看",
                source.get("url", ""),
                source.get("name", ""),
                source.get("category", ""),
                source.get("notes", "没有稳定 RSS，待人工查看。"),
            )
        ]
    if not allow_network:
        return [
            make_manual_item(
                f"{source.get('name', 'Unknown source')}：dry-run 未联网抓取",
                source.get("url", rss_url),
                source.get("name", ""),
                source.get("category", ""),
                "dry-run 模式默认不联网；真实运行时会抓取 RSS。",
            )
        ]
    try:
        raw = fetch_url(rss_url, timeout=timeout)
        items = _parse_with_feedparser(raw, source, limit)
        if not items:
            items = _parse_with_stdlib(raw, source, limit)
        return items or [
            make_manual_item(
                f"{source.get('name', 'Unknown source')}：RSS 暂无可解析条目",
                source.get("url", rss_url),
                source.get("name", ""),
                source.get("category", ""),
                "RSS 已访问但没有解析到条目，待人工查看。",
            )
        ]
    except Exception as exc:
        item = make_manual_item(
            f"{source.get('name', 'Unknown source')}：抓取失败，待人工查看",
            source.get("url", rss_url),
            source.get("name", ""),
            source.get("category", ""),
            f"RSS 抓取失败：{exc}",
        )
        item["fetch_error"] = str(exc)
        return [item]


def fetch_rss_sources(
    sources: List[Dict[str, Any]],
    limit_per_source: int = 3,
    timeout: int = 10,
    allow_network: bool = True,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for source in sources:
        items.extend(fetch_rss_source(source, limit_per_source, timeout, allow_network))
    return items
