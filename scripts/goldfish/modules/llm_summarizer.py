"""LLM summarizer with rule-based fallback.

API keys are read only from environment variables. The agent never writes keys
to disk and never invents sources or opinions when the LLM is unavailable.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .providers.registry import get_provider, resolve_llm_connection
from .utils import truncate


SUMMARY_FIELDS = [
    "one_sentence_summary",
    "why_important",
    "value_for_me",
    "action",
    "suggested_location",
    "core_point",
    "inspiration",
]


def rule_based_summary(item: Dict[str, Any], prompts_config: Dict[str, Any] | None = None) -> Dict[str, str]:
    prompts_config = prompts_config or {}
    category = item.get("category", "other")
    locations = prompts_config.get("fallback_suggested_locations", {})
    title = item.get("title", "未命名信息")
    summary = truncate(item.get("summary") or item.get("raw_content") or "暂无摘要。", 220)
    if item.get("needs_manual_review"):
        one_sentence = f"该来源需要人工查看：{title}"
        why = "当前没有稳定自动抓取结果，需要手动确认是否有高价值更新。"
        action = "打开链接人工查看；只沉淀有公开来源、可复用的信息。"
    else:
        one_sentence = summary if summary != "暂无摘要。" else f"公开来源更新：{title}"
        why = "命中配置的信息源或关键词，可能对 AI 应用开发、Agent/RAG 或技术变现有参考价值。"
        action = "阅读原文，提炼可复用观点、Prompt、项目想法或商业机会。"
    return {
        "one_sentence_summary": one_sentence,
        "why_important": why,
        "value_for_me": "可作为 AI 趋势观察、技术选型、知识库沉淀或商业灵感的候选材料。",
        "action": action,
        "suggested_location": locations.get(category, "[[00_Inbox]]"),
        "core_point": one_sentence,
        "inspiration": "先验证原文，再决定是否沉淀为永久笔记、Prompt、项目灵感或商业想法。",
    }


def _call_openai_compatible(
    item: Dict[str, Any],
    settings: Dict[str, Any],
    prompts_config: Dict[str, Any],
) -> Dict[str, str]:
    payload = {
        "title": item.get("title", ""),
        "source": item.get("source_name") or item.get("source", ""),
        "url": item.get("url", ""),
        "published": item.get("published", ""),
        "summary": item.get("summary", ""),
        "category": item.get("category", ""),
        "score": item.get("score", 0),
    }
    parsed = get_provider(settings).generate_json(
        [
            {"role": "system", "content": prompts_config.get("system_prompt", "")},
            {
                "role": "user",
                "content": prompts_config.get("daily_item_prompt", "")
                + "\n\n输入：\n"
                + json.dumps(payload, ensure_ascii=False),
            },
        ],
        temperature=0.2,
    )
    return {field: str(parsed.get(field, "") or "") for field in SUMMARY_FIELDS}


def summarize_item(
    item: Dict[str, Any],
    settings: Dict[str, Any],
    prompts_config: Dict[str, Any],
    use_llm: bool = True,
) -> Dict[str, Any]:
    if not use_llm or not settings.get("use_llm", True):
        item.update(rule_based_summary(item, prompts_config))
        item["summary_mode"] = "rule"
        return item
    try:
        summary = _call_openai_compatible(item, settings, prompts_config)
        fallback = rule_based_summary(item, prompts_config)
        for field in SUMMARY_FIELDS:
            item[field] = summary.get(field) or fallback[field]
        item["summary_mode"] = "llm"
    except Exception as exc:
        item.update(rule_based_summary(item, prompts_config))
        item["summary_mode"] = "rule"
        item["llm_error"] = str(exc)
    return item


def summarize_items(
    items: List[Dict[str, Any]],
    settings: Dict[str, Any],
    prompts_config: Dict[str, Any],
    use_llm: bool = True,
) -> List[Dict[str, Any]]:
    return [summarize_item(item, settings, prompts_config, use_llm) for item in items]
