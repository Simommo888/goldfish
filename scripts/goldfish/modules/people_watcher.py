"""Track public professional updates from configured AI people."""

from __future__ import annotations

from typing import Any, Dict, List

from .rss_fetcher import fetch_rss_source
from .utils import make_manual_item


SUPPORTED_SOURCE_TYPES = {
    "blog",
    "rss",
    "github",
    "youtube",
    "newsletter",
    "company_news",
    "x_manual",
}


def _manual_person_item(person: Dict[str, Any], source: Dict[str, Any], reason: str) -> Dict[str, Any]:
    item = make_manual_item(
        f"{person.get('name', 'Unknown person')}：{source.get('name', '公开来源')} 待人工查看",
        source.get("url", ""),
        source.get("name", ""),
        "people",
        reason,
    )
    item.update(
        {
            "person_name": person.get("name", ""),
            "person_category": person.get("category", ""),
            "person_priority": person.get("priority", 1),
            "topics": person.get("topics", []),
            "source": source.get("name", ""),
            "content_type": "people",
            "notes": reason,
        }
    )
    return item


def watch_people(
    people: List[Dict[str, Any]],
    limit_per_source: int = 2,
    timeout: int = 10,
    allow_network: bool = True,
) -> List[Dict[str, Any]]:
    updates: List[Dict[str, Any]] = []
    for person in people:
        if not person.get("enabled", True):
            continue
        for source in person.get("sources", []):
            source_type = source.get("type", "")
            if source_type not in SUPPORTED_SOURCE_TYPES:
                updates.append(_manual_person_item(person, source, f"未知来源类型 {source_type}，待人工查看。"))
                continue
            if source.get("rss_url"):
                rss_source = {
                    "name": source.get("name") or person.get("name"),
                    "category": "people",
                    "priority": person.get("priority", 1),
                    "url": source.get("url", ""),
                    "rss_url": source.get("rss_url", ""),
                    "content_type": "people",
                }
                for item in fetch_rss_source(rss_source, limit_per_source, timeout, allow_network):
                    item.update(
                        {
                            "person_name": person.get("name", ""),
                            "person_category": person.get("category", ""),
                            "person_priority": person.get("priority", 1),
                            "topics": person.get("topics", []),
                            "source": source.get("name", ""),
                            "content_type": "people",
                            "notes": source.get("notes", ""),
                        }
                    )
                    updates.append(item)
            else:
                updates.append(_manual_person_item(person, source, source.get("notes", "待人工查看。")))
    return updates
