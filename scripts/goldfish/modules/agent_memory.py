"""Persistent memory for the AI intelligence and knowledge agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from .storage import save_json
from .utils import contains_any, item_text, kb_root, stable_hash, today_string


DEFAULT_MEMORY: Dict[str, Any] = {
    "schema_version": 1,
    "agent_name": "goldfish",
    "mission": "收集公开 AI 情报，并帮助用户沉淀成知识资产。",
    "preferred_topics": [
        "Agent",
        "RAG",
        "AI Coding",
        "Codex",
        "Claude Code",
        "MCP",
        "Knowledge Base",
        "AI 应用开发",
        "技术变现"
    ],
    "ignored_topics": [
        "gossip",
        "rumor",
        "drama",
        "private life",
        "fan war",
        "无来源爆料",
        "私人生活",
        "八卦"
    ],
    "high_value_sources": [],
    "saved_item_hashes": [],
    "rejected_item_hashes": [],
    "topic_scores": {},
    "run_history": []
}


def memory_path(root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "scripts" / "goldfish" / "output_cache" / "agent_memory.json"


def load_memory(root: Path | None = None) -> Dict[str, Any]:
    path = memory_path(root)
    if not path.exists():
        return dict(DEFAULT_MEMORY)
    try:
        import json

        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_MEMORY)
    memory = dict(DEFAULT_MEMORY)
    memory.update(loaded if isinstance(loaded, dict) else {})
    return memory


def save_memory(memory: Dict[str, Any], root: Path | None = None) -> Path:
    return save_json(memory_path(root), memory)


def item_hash(item: Dict[str, Any]) -> str:
    return stable_hash(f"{item.get('url', '')}|{item.get('title', '')}")


def memory_preference_score(item: Dict[str, Any], memory: Dict[str, Any]) -> float:
    text = item_text(item)
    preferred_hits = contains_any(text, memory.get("preferred_topics", []))
    ignored_hits = contains_any(text, memory.get("ignored_topics", []))
    score = len(preferred_hits) * 1.5 - len(ignored_hits) * 2
    source = item.get("source_name") or item.get("source")
    if source and source in memory.get("high_value_sources", []):
        score += 2
    if item_hash(item) in set(memory.get("rejected_item_hashes", [])):
        score -= 5
    return score


def apply_memory_preferences(items: List[Dict[str, Any]], memory: Dict[str, Any]) -> List[Dict[str, Any]]:
    for item in items:
        boost = memory_preference_score(item, memory)
        if boost:
            item["memory_score"] = round(boost, 2)
            item["score"] = round(float(item.get("score", 0)) + boost, 2)
            item.setdefault("score_reasons", []).append(f"{boost:+.1f} Agent 记忆偏好加权")
    return items


def update_memory_from_run(
    memory: Dict[str, Any],
    date_text: str,
    items: List[Dict[str, Any]],
    insights: List[Dict[str, Any]],
) -> Dict[str, Any]:
    topic_scores = dict(memory.get("topic_scores", {}))
    for item in items:
        category = item.get("category", "other")
        topic_scores[category] = round(float(topic_scores.get(category, 0)) + float(item.get("score", 0)), 2)

    high_value_sources = list(memory.get("high_value_sources", []))
    for item in items:
        if item.get("score", 0) >= 8 and item.get("source_name"):
            source = item["source_name"]
            if source not in high_value_sources:
                high_value_sources.append(source)

    run_history = list(memory.get("run_history", []))
    run_history.append(
        {
            "date": date_text,
            "items": len(items),
            "insights": len(insights),
            "top_titles": [item.get("title", "") for item in sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:5]]
        }
    )
    memory["topic_scores"] = topic_scores
    memory["high_value_sources"] = high_value_sources[:50]
    memory["run_history"] = run_history[-30:]
    memory["updated_at"] = today_string()
    return memory
