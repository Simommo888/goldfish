"""Route natural-language goals to goldfish skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .skill_loader import load_skill


@dataclass(frozen=True)
class SkillRule:
    name: str
    keywords: tuple[str, ...]
    reason: str


SKILL_RULES = (
    SkillRule(
        "retrieval-planning",
        ("research", "investigate", "study", "search", "find", "检索", "研究", "搜索", "查找"),
        "Goal asks for retrieval planning or information discovery.",
    ),
    SkillRule(
        "internet-search",
        ("web", "internet", "online", "tavily", "jina", "duckduckgo", "联网", "全网", "网页"),
        "Goal asks for public internet search provider selection.",
    ),
    SkillRule(
        "web-research",
        ("market", "trend", "opportunity", "competitor", "product", "source", "市场", "趋势", "机会", "竞品", "产品"),
        "Goal asks for public web research or market/source investigation.",
    ),
    SkillRule(
        "business-idea",
        ("business idea", "startup", "mvp", "pricing", "monetization", "商业想法", "创业", "变现", "收费", "商业机会"),
        "Goal asks to extract business ideas, MVPs, pricing, or validation plans.",
    ),
    SkillRule(
        "draft-writing",
        ("draft", "write note", "permanent note", "prompt", "草稿", "永久笔记", "笔记", "提示词", "Prompt"),
        "Goal asks to write reusable knowledge drafts, notes, or prompts.",
    ),
    SkillRule(
        "knowledge-routing",
        ("where to save", "organize", "route", "knowledge base", "沉淀", "知识库", "放到哪里", "归档"),
        "Goal asks where findings should be deposited in the knowledge base.",
    ),
    SkillRule(
        "trend-analysis",
        ("trend", "weekly", "signal", "趋势", "周报", "信号"),
        "Goal asks for trend analysis or repeated signal interpretation.",
    ),
    SkillRule(
        "fact-checking",
        ("verify", "fact check", "is it true", "核验", "事实检查", "真实吗", "真假"),
        "Goal asks to verify claims against evidence.",
    ),
    SkillRule(
        "source-evaluation",
        ("source quality", "reliable", "source health", "来源", "信源", "可靠", "健康度"),
        "Goal asks to evaluate source quality or reliability.",
    ),
    SkillRule(
        "external-cli-tools",
        ("cli", "bash", "shell", "rg", "ripgrep", "git", "命令行", "外部工具"),
        "Goal asks for allow-listed external CLI tool usage.",
    ),
    SkillRule(
        "weekly-review",
        ("weekly review", "week", "本周", "每周", "周复盘"),
        "Goal asks for weekly review.",
    ),
)


def select_skills(goal: str, *, limit: int = 4) -> List[Dict[str, Any]]:
    lowered = (goal or "").lower()
    selected: List[Dict[str, Any]] = []
    for rule in SKILL_RULES:
        hits = [keyword for keyword in rule.keywords if keyword.lower() in lowered]
        if not hits:
            continue
        try:
            skill = load_skill(rule.name)
        except Exception:
            continue
        selected.append(
            {
                "name": rule.name,
                "title": skill.get("title", rule.name),
                "path": skill.get("path", ""),
                "reason": rule.reason,
                "matched_keywords": hits[:6],
                "content_preview": _preview(skill.get("content", "")),
            }
        )
    if not selected and lowered.strip():
        try:
            skill = load_skill("retrieval-planning")
            selected.append(
                {
                    "name": "retrieval-planning",
                    "title": skill.get("title", "retrieval-planning"),
                    "path": skill.get("path", ""),
                    "reason": "Default skill for ambiguous natural-language goals.",
                    "matched_keywords": [],
                    "content_preview": _preview(skill.get("content", "")),
                }
            )
        except Exception:
            return []
    return selected[:limit]


def _preview(text: str, max_chars: int = 700) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."
