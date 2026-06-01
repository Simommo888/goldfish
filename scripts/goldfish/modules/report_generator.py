"""Markdown daily report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from .utils import agent_dir


EMPTY_MESSAGE = "今日暂无高质量自动抓取内容，请检查 sources.json 或人工查看待查看来源。"


def _value(item: Dict[str, Any], key: str, default: str = "") -> str:
    value = item.get(key)
    if isinstance(value, list):
        return "；".join(str(part) for part in value)
    return str(value if value not in {None, ""} else default)


def format_news_item(item: Dict[str, Any], index: int) -> str:
    return f"""### {index}. {_value(item, "title", "未命名信息")}

**来源：** {_value(item, "source_name", _value(item, "source", "未知来源"))}  
**分类：** {_value(item, "category", "other")}  
**链接：** {_value(item, "url", "无")}  
**发布时间：** {_value(item, "published", "未知")}  
**一句话总结：** {_value(item, "one_sentence_summary", "暂无摘要")}  
**为什么重要：** {_value(item, "why_important", "待进一步判断")}  
**对我有什么用：** {_value(item, "value_for_me", "可作为候选信息源")}  
**建议行动：** {_value(item, "action", "阅读原文后再沉淀")}  
**建议存放位置：** {_value(item, "suggested_location", "[[00_Inbox]]")}  
**评分：** {_value(item, "score", "0")}  
**评分原因：** {_value(item, "score_reasons", "无")}

---"""


def format_people_item(item: Dict[str, Any], index: int | None = None) -> str:
    heading = f"{item.get('person_name', '未知人物')}：{item.get('title', '未命名动态')}"
    if index is not None:
        heading = f"{index}. {heading}"
    return f"""### {heading}

**来源：** {_value(item, "source_name", _value(item, "source", "未知来源"))}  
**链接：** {_value(item, "url", "无")}  
**发布时间：** {_value(item, "published", "未知")}  
**人物分类：** {_value(item, "person_category", "unknown")}  
**一句话总结：** {_value(item, "one_sentence_summary", "暂无摘要")}  
**核心观点：** {_value(item, "core_point", "待阅读原文确认")}  
**为什么重要：** {_value(item, "why_important", "待进一步判断")}  
**对我的启发：** {_value(item, "inspiration", "可作为候选观察材料")}  
**建议存放位置：** {_value(item, "suggested_location", "[[00_Inbox]]")}  
**建议行动：** {_value(item, "action", "阅读原文后再沉淀")}  
**评分：** {_value(item, "score", "0")}

---"""


def _section(items: Iterable[Dict[str, Any]], formatter, empty: str = EMPTY_MESSAGE) -> str:
    material = list(items)
    if not material:
        return empty
    return "\n\n".join(formatter(item, index) for index, item in enumerate(material, start=1))


def _top(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("score", 0), reverse=True)[:limit]


def _load_template(template_path: Path | None = None) -> str:
    template_path = template_path or agent_dir() / "templates" / "daily_report_template.md"
    return template_path.read_text(encoding="utf-8")


def generate_daily_report(
    date_text: str,
    items: List[Dict[str, Any]],
    people_items: List[Dict[str, Any]],
    template_path: Path | None = None,
) -> str:
    non_manual = [item for item in items if not item.get("needs_manual_review")]
    manual = [item for item in items if item.get("needs_manual_review")]
    template = _load_template(template_path)

    model_product = [item for item in items if item.get("category") in {"model", "product"}]
    agent_rag_coding = [item for item in items if item.get("category") in {"agent", "rag", "ai_coding"}]
    open_source = [item for item in items if item.get("category") == "open_source"]
    papers = [item for item in items if item.get("content_type") == "paper" or item.get("category") == "research"]
    business = [item for item in items if item.get("category") == "business"]

    best_item = _top(non_manual or items, 1)
    best_person = _top(people_items, 1)

    replacements = {
        "{{date}}": date_text,
        "{{top_items}}": _section(_top(non_manual, 5), format_news_item),
        "{{people_items}}": _section(_top(people_items, 5), format_people_item),
        "{{model_product_items}}": _section(_top(model_product, 5), format_news_item),
        "{{agent_rag_coding_items}}": _section(_top(agent_rag_coding, 5), format_news_item),
        "{{open_source_items}}": _section(_top(open_source, 5), format_news_item),
        "{{paper_items}}": _section(_top(papers, 5), format_news_item),
        "{{business_items}}": _section(_top(business, 5), format_news_item),
        "{{manual_review_items}}": _section(manual[:20], format_news_item, "今日没有待人工查看条目。"),
        "{{best_item}}": best_item[0].get("title", EMPTY_MESSAGE) if best_item else EMPTY_MESSAGE,
        "{{best_person}}": best_person[0].get("person_name", "今日暂无明确人物动态") if best_person else "今日暂无明确人物动态",
        "{{best_action}}": best_item[0].get("action", "阅读高分条目并沉淀一条永久笔记") if best_item else "检查信息源配置",
    }
    report = template
    for placeholder, value in replacements.items():
        report = report.replace(placeholder, value)
    return report


def generate_people_report(date_text: str, people_items: List[Dict[str, Any]]) -> str:
    body = _section(
        sorted(people_items, key=lambda item: item.get("score", 0), reverse=True),
        format_people_item,
        "今日暂无可自动确认的 AI 大佬公开专业动态；请人工查看 people.json 中标记的来源。",
    )
    return f"""# AI 大佬动态 - {date_text}

> 只追踪公开、专业、可引用的信息；不追踪私人生活、八卦和粉丝争论。

{body}
"""
