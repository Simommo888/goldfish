"""Deduplicate fetched items by URL, title hash, and title similarity."""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import simple_similarity, stable_hash


def _score(item: Dict[str, Any]) -> float:
    try:
        return float(item.get("score", 0))
    except Exception:
        return 0.0


def _prefer(existing: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    if _score(candidate) > _score(existing):
        return candidate
    if len(str(candidate.get("summary", ""))) > len(str(existing.get("summary", ""))) and _score(candidate) == _score(existing):
        return candidate
    return existing


def deduplicate_items(items: List[Dict[str, Any]], similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
    by_url: Dict[str, Dict[str, Any]] = {}
    by_title_hash: Dict[str, Dict[str, Any]] = {}
    result: List[Dict[str, Any]] = []

    for item in items:
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        title_hash = stable_hash(title) if title else ""

        if url and url in by_url:
            winner = _prefer(by_url[url], item)
            by_url[url].update(winner)
            continue

        if title_hash and title_hash in by_title_hash:
            winner = _prefer(by_title_hash[title_hash], item)
            by_title_hash[title_hash].update(winner)
            continue

        similar_existing = None
        if title:
            for existing in result:
                if simple_similarity(title, existing.get("title", "")) >= similarity_threshold:
                    similar_existing = existing
                    break
        if similar_existing is not None:
            winner = _prefer(similar_existing, item)
            similar_existing.update(winner)
            continue

        result.append(item)
        if url:
            by_url[url] = item
        if title_hash:
            by_title_hash[title_hash] = item

    return result
