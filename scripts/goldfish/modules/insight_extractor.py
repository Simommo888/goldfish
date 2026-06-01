"""Extract knowledge-deposition insights from scored AI news items."""

from __future__ import annotations

from typing import Any, Dict, List

from .agent_memory import memory_preference_score
from .utils import truncate


TARGETS = {
    "permanent_note": {
        "label": "永久笔记",
        "folder": "05_Permanent-Notes/AI-Trends",
        "reason": "可以形成长期观点或方法论。"
    },
    "business_idea": {
        "label": "商业想法",
        "folder": "11_Business-Ideas/AI-News-Inspirations",
        "reason": "可能转化为产品、服务、变现场景或客户需求。"
    },
    "prompt": {
        "label": "Prompt",
        "folder": "09_Prompts/AI-News",
        "reason": "可以沉淀为可复用提示词或工作流。"
    },
    "project_idea": {
        "label": "项目灵感",
        "folder": "02_Projects/AI-News-Ideas",
        "reason": "可以转化为 Demo、作品集项目或工具。"
    }
}


def _target_for_item(item: Dict[str, Any]) -> str:
    category = item.get("category", "other")
    text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('value_for_me', '')}".lower()
    if category == "business" or any(word in text for word in ["pricing", "enterprise", "saas", "customer", "monetization", "商业", "客户", "定价"]):
        return "business_idea"
    if category in {"agent", "rag", "ai_coding", "tool", "open_source"}:
        return "project_idea"
    if any(word in text for word in ["prompt", "workflow", "checklist", "工作流", "提示词"]):
        return "prompt"
    return "permanent_note"


def extract_insights(
    items: List[Dict[str, Any]],
    memory: Dict[str, Any],
    limit: int = 8,
    min_score: float = 5,
) -> List[Dict[str, Any]]:
    candidates = []
    for item in items:
        if item.get("needs_manual_review"):
            continue
        score = float(item.get("score", 0)) + memory_preference_score(item, memory)
        if score < min_score:
            continue
        target_key = _target_for_item(item)
        target = TARGETS[target_key]
        candidates.append(
            {
                "title": item.get("title", "未命名情报"),
                "source": item.get("source_name") or item.get("source", "未知来源"),
                "url": item.get("url", ""),
                "category": item.get("category", "other"),
                "score": round(score, 2),
                "target_type": target_key,
                "target_label": target["label"],
                "target_folder": target["folder"],
                "reason": target["reason"],
                "summary": item.get("one_sentence_summary") or truncate(item.get("summary", ""), 180),
                "why_important": item.get("why_important", "待进一步判断。"),
                "value_for_me": item.get("value_for_me", "可作为候选知识资产。"),
                "suggested_action": item.get("action", "阅读原文，提炼可复用内容。"),
                "source_item": item,
            }
        )
    candidates.sort(key=lambda insight: insight["score"], reverse=True)
    return candidates[:limit]
