"""Keyword and source based scoring for AI intelligence items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .utils import contains_any, item_text, now


MAJOR_LAUNCH_TERMS = [
    "new model",
    "launch",
    "released",
    "release",
    "announced",
    "introducing",
    "product launch",
    "新模型",
    "发布",
    "推出",
]

IMPORTANT_TECH_TERMS = [
    "paper",
    "research",
    "benchmark",
    "blog",
    "keynote",
    "talk",
    "论文",
    "研究",
]

OPEN_SOURCE_TERMS = ["github", "open source", "repo", "library", "framework", "开源"]


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def score_item(item: Dict[str, Any], keywords_config: Dict[str, Any], timezone_name: str = "Asia/Shanghai") -> Dict[str, Any]:
    text = item_text(item)
    text_lower = text.lower()
    score = 0.0
    reasons: List[str] = []

    high_hits = contains_any(text, keywords_config.get("high_priority_keywords", []))
    medium_hits = contains_any(text, keywords_config.get("medium_priority_keywords", []))
    business_hits = contains_any(text, keywords_config.get("business_keywords", []))
    negative_hits = contains_any(text, keywords_config.get("negative_keywords", []))
    focus_hits = contains_any(text, keywords_config.get("focus_directions", []))

    if any(term in text_lower for term in MAJOR_LAUNCH_TERMS):
        score += 5
        reasons.append("+5 发布新模型/新产品/重要动态")
    if any(term in text_lower for term in IMPORTANT_TECH_TERMS) or item.get("content_type") == "paper":
        score += 4
        reasons.append("+4 重要技术观点/论文/博客/演讲")
    if high_hits:
        score += 4
        reasons.append("+4 命中高优先级方向：" + ", ".join(high_hits[:5]))
    if business_hits:
        score += 3
        reasons.append("+3 涉及商业化/创业/产品机会：" + ", ".join(business_hits[:5]))
    if item.get("content_type") == "open_source" or item.get("source_category") == "open_source":
        score += 3
        reasons.append("+3 热门开源项目或开源来源")
    if "github" in text_lower:
        score += 2
        reasons.append("+2 GitHub 项目更新")
    if medium_hits:
        score += 1
        reasons.append("+1 命中中优先级关键词：" + ", ".join(medium_hits[:5]))
    if focus_hits:
        score += 2
        reasons.append("+2 命中你的重点方向：" + ", ".join(focus_hits[:5]))

    if negative_hits:
        penalty = -5 if any(hit in {"gossip", "private life", "celebrity gossip", "fan war"} for hit in negative_hits) else -3
        score += penalty
        reasons.append(f"{penalty} 命中负面过滤词：" + ", ".join(negative_hits[:5]))

    source_priority = item.get("source_priority") or item.get("priority") or 1
    try:
        source_weight = min(float(source_priority), 5.0) * 0.4
        score += source_weight
        reasons.append(f"+{source_weight:.1f} 来源优先级加权")
    except Exception:
        pass

    person_priority = item.get("person_priority")
    if person_priority:
        try:
            person_weight = min(float(person_priority), 5.0) * 0.5
            score += person_weight
            reasons.append(f"+{person_weight:.1f} 人物优先级加权")
        except Exception:
            pass

    published = _parse_date(str(item.get("published", "")))
    if published:
        age_days = (now(timezone_name) - published.astimezone(now(timezone_name).tzinfo)).days
        if age_days <= 2:
            score += 2
            reasons.append("+2 发布时间较新")
        elif age_days <= 7:
            score += 1
            reasons.append("+1 最近一周内容")

    if item.get("needs_manual_review"):
        score = min(score, 2.0)
        reasons.append("待人工查看：不做高分推荐，避免把占位内容当事实")

    if not reasons:
        score += 1
        reasons.append("+1 普通技术动态")

    item["score"] = round(score, 2)
    item["score_reasons"] = reasons
    return item


def score_items(
    items: List[Dict[str, Any]],
    keywords_config: Dict[str, Any],
    timezone_name: str = "Asia/Shanghai",
) -> List[Dict[str, Any]]:
    return [score_item(item, keywords_config, timezone_name) for item in items]
