"""Manual-review placeholders for sources without stable RSS.

First version deliberately avoids complex crawling. It does not log in, does not
store cookies, and does not bypass anti-scraping controls.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import make_manual_item


def build_manual_review_items(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for source in sources:
        if source.get("rss_url"):
            continue
        items.append(
            make_manual_item(
                f"{source.get('name', 'Unknown source')}：待人工查看",
                source.get("url", ""),
                source.get("name", ""),
                source.get("category", ""),
                source.get("notes", "没有稳定 RSS，待人工查看。"),
            )
        )
    return items
