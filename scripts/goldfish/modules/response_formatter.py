"""Goldfish response rendering.

goldfish answers should feel like the startup page continued into the chat:
dark terminal, orange titles, cyan evidence, green actions, compact panels, and
wrapped text. The functions below keep model/tool output stable without turning
the CLI into a raw JSON or raw Markdown dump.
"""

from __future__ import annotations

import os
import re
import shutil
import textwrap
import unicodedata
from typing import Any, Dict, List

from .config_loader import load_config
from .model_setup import redact_secret_text


ORANGE = "#ff9418"
ORANGE_LIGHT = "#ffb45c"
AQUA = "#7ee8ff"
GREEN = "#74e875"
CREAM = "#f4ead2"
MUTED = "#8a9096"
BORDER = "#5f6a70"
DIM = "#5f666d"

DEFAULT_SECTIONS = [
    {"key": "direct_answer", "heading": "结论", "required": True},
    {"key": "context", "heading": "关键依据", "required": False},
    {"key": "judgment", "heading": "我的判断", "required": False},
    {"key": "next_actions", "heading": "下一步", "required": True},
]


def infer_response_kind(text: str) -> str:
    lowered = (text or "").lower()
    if any(word in lowered for word in ["business", "startup", "monetization", "pricing", "mvp", "商业", "创业", "变现", "收费"]):
        return "business_idea"
    if any(word in lowered for word in ["prompt", "提示词"]):
        return "prompt"
    if any(word in lowered for word in ["research", "study", "investigate", "trend", "market", "opportunity", "source", "evidence", "研究", "调研", "趋势", "市场", "机会", "来源"]):
        return "research"
    return "default"


def response_system_prompt(kind: str = "default", language: str = "zh-CN") -> str:
    config = load_config()
    formats = config.response_formats or {}
    template = _template(kind, formats)
    global_rules = formats.get("global_rules") or []
    sections = template.get("sections") or DEFAULT_SECTIONS
    section_lines = "\n".join(
        f"- [{section.get('heading', section.get('key'))}] key={section.get('key')}; required={bool(section.get('required'))}"
        for section in sections
    )
    rules = "\n".join(f"- {rule}" for rule in global_rules)
    return (
        "You are goldfish, a local CLI intelligence and knowledge-deposition agent.\n"
        "Use the fixed Goldfish response frame. Return readable terminal-style Markdown, not raw JSON.\n"
        "Do not use Markdown heading markers like ## unless the user asks for a document.\n"
        "Do not mention that you are following a template.\n"
        "Do not use emoji as layout markers.\n"
        f"Reply language: {language}.\n\n"
        "Preferred visible frame:\n"
        f"goldfish · {template.get('mode', kind)}\n"
        "status: ready · answer: grounded\n"
        "[结论]\n[关键依据]\n[判断]\n[下一步]\n\n"
        "Required section order:\n"
        f"{section_lines}\n\n"
        "Global rules:\n"
        f"{rules}\n\n"
        "If a required section has no evidence, write a short limitation instead of inventing content."
    )


def render_markdown(kind: str, values: Dict[str, Any], *, status: str = "ready", color: bool = False) -> str:
    """Render a compact terminal card.

    The name is kept for compatibility with older tests and call sites. With
    color=False the output is Markdown-safe enough for task files; with
    color=True it uses ANSI truecolor for interactive CLI output.
    """

    formats = load_config().response_formats or {}
    template = _template(kind, formats)
    mode = str(template.get("mode") or kind)
    width = _target_width()
    sections = template.get("sections") or DEFAULT_SECTIONS
    lines = _header(mode, status, width, color=color)
    for section in sections:
        key = str(section.get("key") or "")
        heading = str(section.get("heading") or key or "内容")
        value = values.get(key)
        if _is_empty(value) and not section.get("required"):
            continue
        lines.extend(_section(heading, value, width, color=color))
    lines.append(_rule(width, color=color))
    return redact_secret_text("\n".join(lines).rstrip() + "\n")


def render_agent_summary(
    goal: str,
    observations: List[Dict[str, Any]],
    next_actions: List[str],
    *,
    files_written: List[str] | None = None,
    color: bool = False,
) -> str:
    successful = [obs for obs in observations if obs.get("success")]
    failed = [obs for obs in observations if not obs.get("success")]
    tools = [str(obs.get("tool") or "unknown") for obs in observations]
    values = {
        "direct_answer": f"已围绕目标完成 {len(observations)} 个步骤：{goal}",
        "execution": [
            f"工具调用：{', '.join(tools) if tools else 'none'}",
            f"成功步骤：{len(successful)}",
            f"降级或失败步骤：{len(failed)}",
        ],
        "observations": [_observation_line(obs) for obs in observations] or ["暂无观察记录。"],
        "files_written": [_short_path(str(path)) for path in (files_written or [])[:8]],
        "next_actions": next_actions,
    }
    return render_markdown("agent", values, color=color)


def format_tool_response(tool_name: str, result: Dict[str, Any], response_hint: str = "") -> str:
    if tool_name == "agent" and isinstance(result.get("agent"), dict):
        agent = result["agent"]
        summary = render_agent_summary(
            str(agent.get("goal") or ""),
            agent.get("observations") if isinstance(agent.get("observations"), list) else [],
            [str(item) for item in agent.get("next_actions", [])],
            files_written=agent.get("files_written") if isinstance(agent.get("files_written"), list) else [],
            color=True,
        )
        meta = _mini_meta(
            [
                ("task_id", str(agent.get("task_id") or "")),
                ("steps", str(agent.get("execution", {}).get("steps_executed", 0))),
                ("workspace", str(agent.get("task_path") or "")),
            ],
            color=True,
        )
        return _with_hint(response_hint, summary + "\n" + meta)
    if tool_name in {"memory_show", "memory_remember", "memory_forget", "memory_review"}:
        return _format_memory(tool_name, result, response_hint)
    if tool_name == "web_search":
        return _format_web_search(result, response_hint)
    if tool_name == "search":
        return _format_local_search(result, response_hint)
    if tool_name in {"rag_query", "rag_search", "rag_status"}:
        return _format_rag(tool_name, result, response_hint)
    return ""


def _format_web_search(result: Dict[str, Any], response_hint: str) -> str:
    results = result.get("results") if isinstance(result.get("results"), list) else []
    query = str(result.get("query") or "")
    provider = str(result.get("provider") or ", ".join(result.get("provider_order", [])) or "configured search")
    values = {
        "direct_answer": f"已使用 {provider} 检索：{query}",
        "evidence": _source_cards(results[:5], color=True) or ["没有拿到可展示的公开结果。"],
        "interpretation": "这些结果是检索线索，不是最终结论；高价值内容需要打开来源核验后再沉淀。",
        "uncertainty": "搜索结果会受搜索源排序、发布时间、网页可访问性和摘要截断影响。",
        "value_for_user": "可作为 AI 情报选题、日报素材或后续 Agent 调研入口。",
        "next_actions": ["打开高相关来源核验原文。", "把可信内容沉淀到永久笔记、商业想法或 Prompt 草稿。"],
        "suggested_locations": ["[[04_Resources/AI-News]]", "[[05_Permanent-Notes/AI-Trends]]"],
    }
    rendered = render_markdown("research", values, color=True)
    return _with_hint(response_hint, rendered)


def _format_memory(tool_name: str, result: Dict[str, Any], response_hint: str) -> str:
    if tool_name == "memory_review":
        counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
        values = {
            "direct_answer": "已完成 memory review。",
            "context": [
                f"long_term_facts: {counts.get('long_term_facts', 0)}",
                f"active_projects: {counts.get('active_projects', 0)}",
                f"business_interests: {counts.get('business_interests', 0)}",
                f"run_history: {counts.get('run_history', 0)}",
            ],
            "judgment": result.get("context", "暂无 memory context。"),
            "next_actions": result.get("suggestions") or ["继续使用 /remember 保存稳定偏好。"],
        }
        return _with_hint(response_hint, render_markdown("default", values, color=True))

    if tool_name == "memory_remember":
        remembered = result.get("remembered") if isinstance(result.get("remembered"), dict) else {}
        values = {
            "direct_answer": "已保存一条长期记忆。",
            "context": [
                f"id: {remembered.get('id', '')}",
                f"kind: {remembered.get('kind', '')}",
                f"text: {remembered.get('text', '')}",
            ],
            "judgment": "后续 LLM 对话和 agent loop 会读取压缩后的 memory context。",
            "next_actions": ["用 /memory review 检查记忆质量。", "用 /forget <id 或关键词> 删除不再需要的记忆。"],
        }
        return _with_hint(response_hint, render_markdown("default", values, color=True))

    if tool_name == "memory_forget":
        values = {
            "direct_answer": f"已移除 {result.get('removed_count', 0)} 条匹配记忆。",
            "context": [str(item.get("text") or item) for item in result.get("removed", [])[:8]] if isinstance(result.get("removed"), list) else [],
            "judgment": "如果删除结果不符合预期，可以用 /memory review 重新检查当前记忆。",
            "next_actions": ["必要时重新 /remember 更准确的偏好或事实。"],
        }
        return _with_hint(response_hint, render_markdown("default", values, color=True))

    memory = result.get("memory") if isinstance(result.get("memory"), dict) else {}
    preferences = memory.get("preferences") if isinstance(memory.get("preferences"), dict) else {}
    facts = memory.get("long_term_facts") if isinstance(memory.get("long_term_facts"), list) else []
    values = {
        "direct_answer": "这是当前 goldfish memory 概览。",
        "context": [
            f"schema: v{memory.get('schema_version', 1)}",
            f"topics: {', '.join(str(item) for item in preferences.get('topics', [])[:8])}",
            f"facts: {len(facts)}",
            f"projects: {len(memory.get('active_projects', []))}",
            f"business interests: {len(memory.get('business_interests', []))}",
        ],
        "judgment": result.get("context") or "使用 /memory context 可查看注入 LLM 的压缩上下文。",
        "next_actions": ["用 /remember <text> 保存偏好。", "用 /memory review 审阅记忆。"],
    }
    return _with_hint(response_hint, render_markdown("default", values, color=True))


def _format_local_search(result: Dict[str, Any], response_hint: str) -> str:
    results = result.get("results") if isinstance(result.get("results"), list) else []
    cards = []
    for index, item in enumerate(results[:5], start=1):
        title = str(item.get("title") or item.get("path") or "Untitled")
        path = str(item.get("path") or "")
        snippet = _clip(str(item.get("snippet") or ""), 260)
        cards.append(_numbered_card(index, title, path, snippet, color=True))
    values = {
        "direct_answer": f"已在本地知识库和 goldfish 记忆中搜索：{result.get('query', '')}",
        "context": cards or ["没有找到匹配记录。"],
        "judgment": "本地搜索适合找历史情报、笔记和会话痕迹；如果需要实时事实，应继续使用 web_search。",
        "next_actions": ["打开命中的 Markdown 或任务记录。", "需要实时信息时继续让 goldfish 联网检索。"],
    }
    rendered = render_markdown("default", values, color=True)
    return _with_hint(response_hint, rendered)


def _format_rag(tool_name: str, result: Dict[str, Any], response_hint: str) -> str:
    if tool_name == "rag_status":
        stats = result.get("stats", {})
        stats_data = stats.get("data") if isinstance(stats, dict) and isinstance(stats.get("data"), dict) else {}
        health = result.get("health", {})
        health_data = health.get("data") if isinstance(health, dict) and isinstance(health.get("data"), dict) else {}
        values = {
            "direct_answer": "已检查本地 RAG 知识库服务。",
            "context": [
                f"base_url: {result.get('base_url', '')}",
                f"health: {health_data.get('status') or health.get('status', 'unknown')}",
                f"documents: {stats_data.get('documents', 0)}",
                f"chunks: {stats_data.get('chunks', 0)}",
                f"embeddings: {stats_data.get('embeddings', 0)}",
                f"kb_root: {stats_data.get('kb_root', '')}",
            ],
            "judgment": "status=ok 表示 goldfish 可以通过 ToolRegistry 调用本地知识库；如果为 error，请先启动 RAG 服务。",
            "next_actions": ["使用 /rag <question> 查询知识库。", "使用 /rag-search <query> 查看命中的原始片段。"],
        }
        return _with_hint(response_hint, render_markdown("default", values, color=True))

    if tool_name == "rag_search":
        sources = result.get("results") if isinstance(result.get("results"), list) else []
        cards = [_rag_source_card(index, item, color=True) for index, item in enumerate(sources[:5], start=1)]
        values = {
            "direct_answer": f"已在本地 RAG 知识库检索：{result.get('query', '')}",
            "context": cards or ["没有找到匹配片段，或 RAG 服务未返回结果。"],
            "judgment": "RAG search 返回的是可引用片段，适合核对来源和定位 Obsidian 原文。",
            "next_actions": ["打开命中的 Markdown 原文核验上下文。", "需要综合回答时使用 /rag <question>。"],
        }
        return _with_hint(response_hint, render_markdown("default", values, color=True))

    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    answer = str(result.get("answer") or result.get("error") or "RAG 没有返回可用回答。")
    cards = [_rag_source_card(index, item, color=True) for index, item in enumerate(sources[:5], start=1)]
    warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    values = {
        "direct_answer": answer,
        "context": cards or ["没有可展示的引用片段。"],
        "judgment": "这是基于本地 RAG/Obsidian 知识库的回答；如果答案很关键，仍建议打开来源片段核验。",
        "next_actions": warnings[:3] + ["把高价值结论沉淀到永久笔记或项目文档。"],
    }
    return _with_hint(response_hint, render_markdown("default", values, color=True))


def _rag_source_card(index: int, item: Dict[str, Any], *, color: bool) -> str:
    title = str(item.get("title") or "Untitled")
    heading = str(item.get("heading") or "")
    path = str(item.get("file_path") or "")
    score = item.get("score", 0)
    detail = path if not heading else f"{path}  >  {heading}"
    body = _clip(str(item.get("content") or ""), 320)
    score_line = f"score: {score}" if score not in {"", None} else ""
    return _numbered_card(index, title, detail, "\n".join(part for part in [score_line, body] if part), color=color)


def _source_cards(items: List[Dict[str, Any]], *, color: bool) -> List[str]:
    cards = []
    for index, item in enumerate(items, start=1):
        title = str(item.get("title") or "Untitled")
        url = str(item.get("url") or "")
        snippet = _clip(str(item.get("snippet") or ""), 300)
        cards.append(_numbered_card(index, title, url, snippet, color=color))
    return cards


def _numbered_card(index: int, title: str, detail: str, body: str, *, color: bool) -> str:
    width = _target_width() - 6
    label = _paint(f"{index:02d}", ORANGE, color)
    title_text = _paint(_clip(title, 92), CREAM, color)
    body_lines = _wrap(body, max(42, width - 6))
    lines = [f"{label}  {title_text}"]
    if detail:
        detail_lines = _wrap(detail, max(42, width - 6), break_long_words=True)
        lines.extend(f"    {_paint(line, AQUA, color)}" for line in detail_lines[:2])
    lines.extend(f"    {line}" for line in body_lines[:3])
    return "\n".join(lines)


def _header(mode: str, status: str, width: int, *, color: bool) -> List[str]:
    title = f" goldfish · {mode} "
    fill = max(1, width - _width(title) - 3)
    top = _paint("╭─", BORDER, color) + _paint(title, ORANGE, color) + _paint("─" * fill + "╮", BORDER, color)
    content = (
        f"{_paint('><(((o>', ORANGE, color)}  "
        f"{_paint('status:', MUTED, color)} {_paint(status, GREEN, color)}  "
        f"{_paint('answer:', MUTED, color)} {_paint('grounded', AQUA, color)}"
    )
    return [top, _framed_line(content, width, color=color), _paint("╰" + "─" * (width - 2) + "╯", BORDER, color), ""]


def _section(heading: str, value: Any, width: int, *, color: bool) -> List[str]:
    label = _paint("▌", ORANGE, color) + " " + _paint(heading, ORANGE_LIGHT, color)
    lines = [label]
    formatted = _format_value(value, width=width, color=color)
    lines.extend(formatted)
    lines.append("")
    return lines


def _format_value(value: Any, *, width: int, color: bool) -> List[str]:
    if _is_empty(value):
        return ["  " + _paint("暂无可验证信息。", MUTED, color)]
    if isinstance(value, list):
        lines: List[str] = []
        for item in value:
            text = _stringify(item)
            if "\n" in text:
                lines.extend("  " + line for line in text.splitlines())
            else:
                bullet = _paint("+", GREEN, color)
                wrapped = _wrap(text, max(36, width - 6))
                if wrapped:
                    lines.append(f"  {bullet} {wrapped[0]}")
                    lines.extend("    " + line for line in wrapped[1:])
        return lines or ["  " + _paint("暂无可验证信息。", MUTED, color)]
    wrapped = _wrap(_stringify(value), max(36, width - 4))
    return ["  " + line for line in wrapped]


def _mini_meta(items: List[tuple[str, str]], *, color: bool) -> str:
    width = _target_width()
    lines = [_paint("▌ 任务工作区", ORANGE_LIGHT, color)]
    for key, value in items:
        wrapped = _wrap(value, max(42, width - 18))
        if not wrapped:
            wrapped = [""]
        lines.append(f"  {_paint(key.ljust(9), MUTED, color)} : {_paint(wrapped[0], AQUA if key == 'workspace' else CREAM, color)}")
        lines.extend(" " * 14 + _paint(line, AQUA, color) for line in wrapped[1:])
    return "\n".join(lines)


def _with_hint(hint: str, body: str) -> str:
    if not hint:
        return body
    return _paint(hint, ORANGE, _use_color()) + "\n" + body


def _rule(width: int, *, color: bool) -> str:
    return _paint("─" * min(width, 112), BORDER, color)


def _template(kind: str, formats: Dict[str, Any]) -> Dict[str, Any]:
    templates = formats.get("templates") if isinstance(formats.get("templates"), dict) else {}
    return templates.get(kind) or templates.get("default") or {"mode": kind, "sections": DEFAULT_SECTIONS}


def _stringify(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{key}: {value[key]}" for key in value)
    return str(value).strip()


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _observation_line(obs: Dict[str, Any]) -> str:
    status = str(obs.get("status") or "")
    tool = str(obs.get("tool") or "")
    success = "ok" if obs.get("success") else "degraded"
    reason = _clip(str(obs.get("reason") or obs.get("error") or ""), 160)
    return f"step {obs.get('step')}: {tool} / {status} / {success} - {reason}"


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _wrap(text: str, width: int, *, break_long_words: bool = False) -> List[str]:
    chunks = []
    for paragraph in str(text or "").splitlines() or [""]:
        paragraph = paragraph.strip()
        if not paragraph:
            chunks.append("")
            continue
        chunks.extend(
            textwrap.wrap(
                paragraph,
                width=width,
                break_long_words=break_long_words,
                break_on_hyphens=break_long_words,
            )
            or [paragraph]
        )
    return chunks


def _target_width() -> int:
    columns = shutil.get_terminal_size((112, 40)).columns
    return max(78, min(columns - 4, 112))


def _paint(text: str, color_hex: str, enabled: bool) -> str:
    if not enabled or not _use_color():
        return text
    color_hex = color_hex.lstrip("#")
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def _framed_line(content: str, width: int, *, color: bool) -> str:
    padding = max(0, width - _width(content) - 4)
    return _paint("│ ", BORDER, color) + content + " " * padding + _paint(" │", BORDER, color)


def _short_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return path


def _use_color() -> bool:
    return not (os.getenv("NO_COLOR") or os.getenv("GOLDFISH_NO_COLOR"))


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _width(text: str) -> int:
    cleaned = ANSI_RE.sub("", text)
    total = 0
    for char in cleaned:
        if unicodedata.combining(char):
            continue
        total += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return total
