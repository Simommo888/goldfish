"""Simple keyword classifier for AI news items."""

from __future__ import annotations

from typing import Any, Dict

from .utils import contains_any, item_text


CATEGORY_ORDER = [
    "agent",
    "rag",
    "ai_coding",
    "model",
    "product",
    "research",
    "open_source",
    "business",
    "people",
    "tool",
    "other",
]


def classify_item(item: Dict[str, Any], keywords_config: Dict[str, Any]) -> str:
    content_type = item.get("content_type")
    if content_type == "people":
        return "people"
    if content_type == "paper":
        return "research"
    if content_type == "open_source":
        return "open_source"
    if content_type == "product":
        return "product"

    source_category = item.get("source_category")
    if source_category in {"research", "open_source", "product"}:
        return source_category

    text = item_text(item)
    category_keywords = keywords_config.get("category_keywords", {})
    scores = {}
    for category in CATEGORY_ORDER:
        hits = contains_any(text, category_keywords.get(category, []))
        if hits:
            scores[category] = len(hits)

    if not scores:
        return "other"

    return sorted(scores.items(), key=lambda pair: (-pair[1], CATEGORY_ORDER.index(pair[0])))[0][0]


def classify_items(items: list[Dict[str, Any]], keywords_config: Dict[str, Any]) -> list[Dict[str, Any]]:
    for item in items:
        item["category"] = classify_item(item, keywords_config)
    return items
