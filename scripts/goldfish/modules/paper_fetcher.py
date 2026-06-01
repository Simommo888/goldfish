"""Fetch AI paper updates from arXiv RSS and manual-review paper sources."""

from __future__ import annotations

from typing import Any, Dict, List

from .rss_fetcher import fetch_rss_source
from .utils import make_manual_item


def fetch_papers(
    sources: List[Dict[str, Any]],
    limit: int = 5,
    timeout: int = 10,
    allow_network: bool = True,
) -> List[Dict[str, Any]]:
    papers: List[Dict[str, Any]] = []
    for source in sources:
        if source.get("rss_url"):
            rss_source = dict(source)
            rss_source["content_type"] = "paper"
            for item in fetch_rss_source(rss_source, limit, timeout, allow_network):
                item["content_type"] = "paper"
                item["category"] = "research"
                item.setdefault("authors", [])
                papers.append(item)
        else:
            item = make_manual_item(
                f"{source.get('name', '论文源')}：待人工查看",
                source.get("url", ""),
                source.get("name", ""),
                "research",
                source.get("notes", "没有稳定 RSS，待人工查看。"),
            )
            item.update({"content_type": "paper", "category": "research", "authors": [], "score": 0})
            papers.append(item)
    return papers[: max(limit, 1) * max(len(sources), 1)]
