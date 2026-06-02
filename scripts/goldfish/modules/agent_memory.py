"""Persistent memory for the goldfish intelligence agent.

The design follows a Codex-like memory stance:

- Explicit: users can inspect, remember, forget, and review memory.
- Bounded: memory is stored in one local JSON file and never stores API keys.
- Useful: compact memory context is injected into LLM/chat and agent planning.
- Reversible: each remembered item has an id and can be removed by query/id.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from .model_setup import redact_secret_text
from .storage import save_json
from .utils import contains_any, item_text, kb_root, stable_hash, today_string


SCHEMA_VERSION = 2

DEFAULT_MEMORY: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "agent_name": "goldfish",
    "mission": "收集公开 AI 情报，并帮助用户沉淀成知识资产。",
    "user_profile": {
        "role": "",
        "goals": [],
        "workflow": "Obsidian-first knowledge deposition",
    },
    "preferences": {
        "language": "zh-CN",
        "answer_style": "concise terminal cards with evidence and next actions",
        "topics": [
            "Agent",
            "RAG",
            "AI Coding",
            "Codex",
            "Claude Code",
            "MCP",
            "Knowledge Base",
            "AI 应用开发",
            "技术变现",
        ],
        "output_targets": [
            "permanent notes",
            "business ideas",
            "prompts",
            "project ideas",
        ],
    },
    "active_projects": [],
    "business_interests": [],
    "writing_style": {
        "tone": "clear, direct, useful",
        "format": "结论 / 依据 / 判断 / 下一步 / 沉淀位置",
    },
    "long_term_facts": [],
    "rejected_topics": [
        "gossip",
        "rumor",
        "drama",
        "private life",
        "fan war",
        "无来源爆料",
        "私人生活",
        "八卦",
    ],
    "high_value_sources": [],
    "saved_item_hashes": [],
    "rejected_item_hashes": [],
    "topic_scores": {},
    "run_history": [],
    "memory_log": [],
}


def memory_path(root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "scripts" / "goldfish" / "output_cache" / "agent_memory.json"


def load_memory(root: Path | None = None) -> Dict[str, Any]:
    path = memory_path(root)
    if not path.exists():
        return deepcopy(DEFAULT_MEMORY)
    try:
        import json

        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(DEFAULT_MEMORY)
    return migrate_memory(loaded if isinstance(loaded, dict) else {})


def migrate_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    migrated = deepcopy(DEFAULT_MEMORY)
    migrated.update(memory)

    old_preferred = memory.get("preferred_topics")
    if isinstance(old_preferred, list):
        topics = list(migrated.get("preferences", {}).get("topics", []))
        for topic in old_preferred:
            if isinstance(topic, str) and topic not in topics:
                topics.append(topic)
        migrated.setdefault("preferences", {})["topics"] = topics

    old_ignored = memory.get("ignored_topics")
    if isinstance(old_ignored, list):
        rejected = list(migrated.get("rejected_topics", []))
        for topic in old_ignored:
            if isinstance(topic, str) and topic not in rejected:
                rejected.append(topic)
        migrated["rejected_topics"] = rejected

    migrated["preferred_topics"] = list(migrated.get("preferences", {}).get("topics", []))
    migrated["ignored_topics"] = list(migrated.get("rejected_topics", []))
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated


def save_memory(memory: Dict[str, Any], root: Path | None = None) -> Path:
    normalized = migrate_memory(memory)
    return save_json(memory_path(root), normalized)


def remember_memory(
    text: str,
    *,
    kind: str = "fact",
    tags: List[str] | None = None,
    root: Path | None = None,
) -> Dict[str, Any]:
    clean = redact_secret_text(" ".join((text or "").split()))
    if not clean:
        return {"status": "error", "error": "memory text is required"}
    memory = load_memory(root)
    item = {
        "id": stable_hash(clean)[:12],
        "kind": kind or _infer_memory_kind(clean),
        "text": clean,
        "tags": tags or _infer_tags(clean),
        "created_at": today_string(),
        "source": "user",
    }
    facts = [entry for entry in memory.get("long_term_facts", []) if entry.get("id") != item["id"]]
    facts.append(item)
    memory["long_term_facts"] = facts[-200:]
    _apply_structured_hint(memory, item)
    _append_memory_log(memory, "remember", item)
    path = save_memory(memory, root)
    return {"status": "ok", "path": str(path), "remembered": item, "summary": memory_context(memory)}


def forget_memory(query: str, *, root: Path | None = None) -> Dict[str, Any]:
    clean = " ".join((query or "").split())
    if not clean:
        return {"status": "error", "error": "forget query is required"}
    memory = load_memory(root)
    removed: List[Dict[str, Any]] = []

    facts = []
    for item in memory.get("long_term_facts", []):
        if _matches_memory(item, clean):
            removed.append(item)
        else:
            facts.append(item)
    memory["long_term_facts"] = facts

    for key in ("active_projects", "business_interests", "high_value_sources"):
        kept = []
        for value in memory.get(key, []):
            if clean.lower() in str(value).lower():
                removed.append({"kind": key, "text": str(value)})
            else:
                kept.append(value)
        memory[key] = kept

    preferences = memory.setdefault("preferences", {})
    topics = []
    for value in preferences.get("topics", []):
        if clean.lower() in str(value).lower():
            removed.append({"kind": "topic", "text": str(value)})
        else:
            topics.append(value)
    preferences["topics"] = topics
    memory["preferred_topics"] = topics

    _append_memory_log(memory, "forget", {"query": clean, "removed_count": len(removed)})
    path = save_memory(memory, root)
    return {"status": "ok", "path": str(path), "removed_count": len(removed), "removed": removed[:20], "summary": memory_context(memory)}


def memory_context(memory: Dict[str, Any] | None = None, *, max_items: int = 8) -> str:
    memory = migrate_memory(memory or load_memory())
    profile = memory.get("user_profile", {})
    preferences = memory.get("preferences", {})
    facts = memory.get("long_term_facts", [])[-max_items:]
    lines = [
        "Goldfish memory context:",
        f"- Mission: {memory.get('mission', '')}",
        f"- Language: {preferences.get('language', 'zh-CN')}",
        f"- Answer style: {preferences.get('answer_style', '')}",
        f"- Focus topics: {', '.join(str(item) for item in preferences.get('topics', [])[:12])}",
        f"- Output targets: {', '.join(str(item) for item in preferences.get('output_targets', [])[:8])}",
    ]
    if profile.get("role"):
        lines.append(f"- User role: {profile.get('role')}")
    if profile.get("goals"):
        lines.append(f"- User goals: {', '.join(str(item) for item in profile.get('goals', [])[:6])}")
    if memory.get("active_projects"):
        lines.append(f"- Active projects: {', '.join(str(item) for item in memory.get('active_projects', [])[:6])}")
    if memory.get("business_interests"):
        lines.append(f"- Business interests: {', '.join(str(item) for item in memory.get('business_interests', [])[:6])}")
    if facts:
        lines.append("- Long-term facts:")
        for item in facts:
            lines.append(f"  - [{item.get('kind', 'fact')}] {item.get('text', '')}")
    return "\n".join(line for line in lines if line.strip())


def review_memory(root: Path | None = None) -> Dict[str, Any]:
    memory = load_memory(root)
    facts = memory.get("long_term_facts", [])
    stale = [item for item in facts if str(item.get("kind")) in {"temporary", "task"}][:10]
    suggestions = []
    if not facts:
        suggestions.append("Use /remember to save durable preferences, projects, and working style.")
    if not memory.get("active_projects"):
        suggestions.append("Save active projects so agent planning can prioritize relevant context.")
    if not memory.get("business_interests"):
        suggestions.append("Save business interests if you want goldfish to surface monetization angles.")
    return {
        "path": str(memory_path(root)),
        "schema_version": memory.get("schema_version"),
        "counts": {
            "long_term_facts": len(facts),
            "active_projects": len(memory.get("active_projects", [])),
            "business_interests": len(memory.get("business_interests", [])),
            "high_value_sources": len(memory.get("high_value_sources", [])),
            "run_history": len(memory.get("run_history", [])),
        },
        "context": memory_context(memory),
        "stale_candidates": stale,
        "suggestions": suggestions,
    }


def item_hash(item: Dict[str, Any]) -> str:
    return stable_hash(f"{item.get('url', '')}|{item.get('title', '')}")


def memory_preference_score(item: Dict[str, Any], memory: Dict[str, Any]) -> float:
    memory = migrate_memory(memory)
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
    memory = migrate_memory(memory)
    for item in items:
        boost = memory_preference_score(item, memory)
        if boost:
            item["memory_score"] = round(boost, 2)
            item["score"] = round(float(item.get("score", 0)) + boost, 2)
            item.setdefault("score_reasons", []).append(f"{boost:+.1f} Agent memory preference boost")
    return items


def update_memory_from_run(
    memory: Dict[str, Any],
    date_text: str,
    items: List[Dict[str, Any]],
    insights: List[Dict[str, Any]],
) -> Dict[str, Any]:
    memory = migrate_memory(memory)
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
            "top_titles": [item.get("title", "") for item in sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:5]],
        }
    )
    memory["topic_scores"] = topic_scores
    memory["high_value_sources"] = high_value_sources[:50]
    memory["run_history"] = run_history[-30:]
    memory["updated_at"] = today_string()
    return memory


def _infer_memory_kind(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["prefer", "关注", "偏好", "喜欢", "style", "format"]):
        return "preference"
    if any(word in lowered for word in ["project", "项目", "goldfish"]):
        return "project"
    if any(word in lowered for word in ["business", "startup", "商业", "创业", "变现"]):
        return "business"
    return "fact"


def _infer_tags(text: str) -> List[str]:
    tags = []
    lowered = text.lower()
    for tag in ["agent", "rag", "ai coding", "mcp", "prompt", "business", "obsidian", "goldfish"]:
        if tag in lowered:
            tags.append(tag.replace(" ", "_"))
    for tag in ["智能体", "商业", "提示词", "知识库", "面试"]:
        if tag in text:
            tags.append(tag)
    return sorted(set(tags))[:8]


def _apply_structured_hint(memory: Dict[str, Any], item: Dict[str, Any]) -> None:
    text = item.get("text", "")
    kind = item.get("kind", "")
    if kind == "project" or "goldfish" in text.lower():
        _append_unique(memory, "active_projects", text)
    if kind == "business":
        _append_unique(memory, "business_interests", text)
    if kind == "preference":
        preferences = memory.setdefault("preferences", {})
        topics = list(preferences.get("topics", []))
        for tag in item.get("tags", []):
            if tag not in topics:
                topics.append(tag)
        preferences["topics"] = topics[-50:]
        memory["preferred_topics"] = preferences["topics"]


def _append_unique(memory: Dict[str, Any], key: str, value: str, limit: int = 50) -> None:
    values = list(memory.get(key, []))
    if value not in values:
        values.append(value)
    memory[key] = values[-limit:]


def _append_memory_log(memory: Dict[str, Any], action: str, payload: Dict[str, Any]) -> None:
    log = list(memory.get("memory_log", []))
    log.append({"action": action, "payload": payload, "created_at": today_string()})
    memory["memory_log"] = log[-100:]


def _matches_memory(item: Dict[str, Any], query: str) -> bool:
    lowered = query.lower()
    return lowered in str(item.get("id", "")).lower() or lowered in str(item.get("text", "")).lower()
