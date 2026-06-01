"""Build source-health records from fetched items."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List

from .utils import now


def build_source_health_records(
    sources: Iterable[Dict[str, Any]],
    items: Iterable[Dict[str, Any]],
    timezone_name: str = "Asia/Shanghai",
) -> List[Dict[str, Any]]:
    source_map: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        name = str(source.get("name", "") or "").strip()
        if name:
            source_map[name] = source

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        name = str(item.get("source_name") or item.get("source") or "").strip()
        if name:
            grouped[name].append(item)

    names = sorted(set(source_map) | set(grouped))
    created = now(timezone_name).isoformat()
    records: List[Dict[str, Any]] = []
    for name in names:
        source_items = grouped.get(name, [])
        errors = [str(item.get("fetch_error")) for item in source_items if item.get("fetch_error")]
        manual_count = sum(1 for item in source_items if item.get("needs_manual_review"))
        real_items = [item for item in source_items if not item.get("needs_manual_review") and not item.get("fetch_error")]
        status = "success" if real_items else "manual_review" if source_items and not errors else "fail" if errors else "not_checked"
        if not source_map.get(name, {}).get("enabled", True):
            status = "disabled"
        quality_score = _quality_score(real_items, manual_count, errors)
        records.append(
            {
                "source_name": name,
                "status": status,
                "error_message": "; ".join(errors[:3]),
                "items_count": len(real_items),
                "manual_review_count": manual_count,
                "quality_score": quality_score,
                "last_success_at": created if real_items else "",
                "created_at": created,
            }
        )
    return records


def _quality_score(items: List[Dict[str, Any]], manual_count: int, errors: List[str]) -> float:
    if errors:
        return 0.0
    if not items:
        return 0.2 if manual_count else 0.0
    average_item_score = sum(float(item.get("score", 0) or 0) for item in items) / max(len(items), 1)
    normalized = min(max(average_item_score / 10.0, 0.0), 1.0)
    volume_bonus = min(len(items), 5) * 0.08
    return round(min(1.0, 0.35 + normalized * 0.5 + volume_bonus), 3)
