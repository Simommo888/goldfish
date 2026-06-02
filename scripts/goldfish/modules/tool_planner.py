"""LLM-backed tool planner for natural-language goldfish requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol

from .config_loader import load_config
from .providers.registry import get_provider, resolve_llm_connection


MIN_CONFIDENCE = 0.45
PLANNER_ALLOWED_TOOLS = {
    "web_search",
    "search",
    "rag_query",
    "rag_search",
    "rag_status",
    "agent",
    "doctor",
    "tools",
    "skills",
    "memory_show",
    "memory_remember",
    "memory_forget",
    "memory_review",
    "history",
    "source_health",
    "feedback_list",
    "config_check",
    "dry_run",
    "run_daily",
    "weekly",
    "external_cli",
}
ARG_ALLOWLIST = {
    "web_search": {"query", "mode", "limit", "fetch_limit", "timeout", "search_provider", "provider", "no_llm", "no_save", "timespan", "fetch_pages"},
    "search": {"query", "limit"},
    "rag_query": {"question", "query", "top_k", "limit", "retrieval_mode", "category", "use_llm"},
    "rag_search": {"query", "question", "top_k", "limit", "retrieval_mode", "category"},
    "agent": {"goal", "max_steps", "no_llm", "no_save", "step_timeout", "task_timeout", "max_failures", "max_consecutive_failures"},
    "memory_remember": {"text", "kind", "tags"},
    "memory_forget": {"query"},
    "dry_run": {"no_llm", "emit_report", "write_drafts", "date", "limit"},
    "run_daily": {"no_llm", "emit_report", "write_drafts", "date", "limit", "dry_run"},
    "weekly": {"no_llm", "emit_report", "date"},
    "skills": {"name"},
    "source_health": {"limit"},
    "history": {"limit"},
    "external_cli": {"action", "name", "args"},
}
NO_ARG_TOOLS = {"doctor", "tools", "memory_show", "memory_review", "feedback_list", "config_check", "rag_status"}


class PlannerProvider(Protocol):
    def generate_json(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, Any]:
        ...


@dataclass(frozen=True)
class ToolPlan:
    tool_name: str
    args: Dict[str, Any]
    response_hint: str
    confidence: float
    reason: str


def plan_tool(
    message: str,
    tools: List[Dict[str, Any]],
    defaults: Dict[str, Any] | None = None,
    *,
    provider: PlannerProvider | None = None,
    settings: Dict[str, Any] | None = None,
    min_confidence: float = MIN_CONFIDENCE,
) -> ToolPlan | None:
    text = (message or "").strip()
    if not text or (defaults or {}).get("no_llm"):
        return None
    settings = _planner_settings(settings, defaults or {})
    if provider is None:
        connection = resolve_llm_connection(settings)
        if not connection.get("api_key"):
            return None
        provider = get_provider(settings)
    try:
        raw = provider.generate_json(_planner_messages(text, tools), temperature=0.0)
    except Exception:
        return None
    return validate_tool_plan(raw, text, tools, defaults or {}, min_confidence=min_confidence)


def validate_tool_plan(
    raw: Dict[str, Any],
    message: str,
    tools: List[Dict[str, Any]],
    defaults: Dict[str, Any] | None = None,
    *,
    min_confidence: float = MIN_CONFIDENCE,
) -> ToolPlan | None:
    defaults = defaults or {}
    tool_name = str(raw.get("tool") or raw.get("tool_name") or "").strip()
    allowed = {str(tool.get("name") or "") for tool in tools} & PLANNER_ALLOWED_TOOLS
    if not tool_name or tool_name not in allowed:
        return None
    confidence = _float(raw.get("confidence"), 0.0)
    if confidence < min_confidence:
        return None
    raw_args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
    normalized_tool = _normalize_tool(tool_name, message)
    args = _sanitize_args(normalized_tool, raw_args, message, defaults)
    return ToolPlan(
        tool_name=normalized_tool,
        args=args,
        response_hint=_response_hint(normalized_tool),
        confidence=confidence,
        reason=str(raw.get("reason") or ""),
    )


def _planner_settings(settings: Dict[str, Any] | None, defaults: Dict[str, Any]) -> Dict[str, Any]:
    resolved = dict(settings or load_config().settings)
    if defaults.get("provider"):
        resolved["llm_provider"] = defaults["provider"]
    if defaults.get("model"):
        resolved["llm_model"] = defaults["model"]
    if defaults.get("base_url"):
        resolved["llm_base_url"] = defaults["base_url"]
    return resolved


def _planner_messages(message: str, tools: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    tool_lines = []
    for tool in tools:
        name = str(tool.get("name") or "")
        if name not in PLANNER_ALLOWED_TOOLS:
            continue
        tool_lines.append(
            f"- {name}: {tool.get('description', '')}; mutating={bool(tool.get('mutating'))}; "
            f"allowed_args={sorted(ARG_ALLOWLIST.get(name, set())) if name not in NO_ARG_TOOLS else []}"
        )
    system = (
        "You are goldfish's tool router. Choose exactly one existing tool for the user request. "
        "Return strict JSON only with keys: tool, args, confidence, reason. "
        "Do not answer the user. Do not invent tools. Use web_search for current/latest/public web information. "
        "Use rag_query for questions about the configured local RAG/Obsidian knowledge base, saved notes, or prior deposited knowledge. "
        "Use rag_search when the user explicitly asks to search source chunks in the RAG knowledge base. "
        "Use search only for goldfish local history/chat/generated reports when RAG is not requested. "
        "Use agent for multi-step research, drafting, business ideas, or knowledge deposition. "
        "Use memory_remember only when the user explicitly asks you to remember/save a durable preference or fact. "
        "Use memory_forget when the user asks to forget/delete a memory. Use memory_review for memory audits. "
        "Use dry_run for daily report requests unless the user explicitly asks to write/save/run for real. "
        "Use external_cli only with action=list unless the user explicitly asks for an allow-listed CLI tool."
    )
    user = f"Available tools:\n" + "\n".join(tool_lines) + f"\n\nUser request:\n{message}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _normalize_tool(tool_name: str, message: str) -> str:
    if tool_name == "run_daily" and not _explicit_real_run(message):
        return "dry_run"
    return tool_name


def _sanitize_args(tool_name: str, raw_args: Dict[str, Any], message: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name in NO_ARG_TOOLS:
        return {}
    allowed = ARG_ALLOWLIST.get(tool_name, set())
    args = {key: value for key, value in raw_args.items() if key in allowed}
    if tool_name == "web_search":
        args["query"] = str(args.get("query") or message).strip()
        if _looks_time_sensitive(message) and "search_provider" not in args and "provider" not in args:
            args["search_provider"] = "news"
        if "limit" in args:
            args["limit"] = _int(args["limit"], 8, min_value=1, max_value=20)
    elif tool_name == "search":
        args["query"] = str(args.get("query") or message).strip()
        if "limit" in args:
            args["limit"] = _int(args["limit"], 8, min_value=1, max_value=50)
    elif tool_name == "rag_query":
        question = str(args.get("question") or args.get("query") or message).strip()
        args = {key: value for key, value in args.items() if key in ARG_ALLOWLIST["rag_query"]}
        args["question"] = question
        if "top_k" in args:
            args["top_k"] = _int(args["top_k"], 8, min_value=1, max_value=20)
        if "limit" in args and "top_k" not in args:
            args["top_k"] = _int(args.pop("limit"), 8, min_value=1, max_value=20)
    elif tool_name == "rag_search":
        query = str(args.get("query") or args.get("question") or message).strip()
        args = {key: value for key, value in args.items() if key in ARG_ALLOWLIST["rag_search"]}
        args["query"] = query
        if "top_k" in args:
            args["top_k"] = _int(args["top_k"], 8, min_value=1, max_value=30)
        if "limit" in args and "top_k" not in args:
            args["top_k"] = _int(args.pop("limit"), 8, min_value=1, max_value=30)
    elif tool_name == "memory_remember":
        args["text"] = str(args.get("text") or message).strip()
        args.setdefault("kind", "fact")
        if isinstance(args.get("tags"), str):
            args["tags"] = [tag.strip() for tag in args["tags"].split(",") if tag.strip()]
    elif tool_name == "memory_forget":
        args["query"] = str(args.get("query") or message).strip()
    elif tool_name == "agent":
        args["goal"] = str(args.get("goal") or message).strip()
        args["max_steps"] = _int(args.get("max_steps", 5), 5, min_value=1, max_value=8)
        if "step_timeout" in args:
            args["step_timeout"] = _float_range(args["step_timeout"], 45.0, min_value=1.0, max_value=600.0)
        if "task_timeout" in args:
            args["task_timeout"] = _float_range(args["task_timeout"], 240.0, min_value=5.0, max_value=7200.0)
        if "max_failures" in args:
            args["max_failures"] = _int(args["max_failures"], 4, min_value=1, max_value=20)
        if "max_consecutive_failures" in args:
            args["max_consecutive_failures"] = _int(args["max_consecutive_failures"], 2, min_value=1, max_value=10)
        args.setdefault("no_save", False)
    elif tool_name == "external_cli":
        if str(args.get("action") or "list").lower() != "list":
            return {"action": "list"}
        args = {"action": "list"}
    elif tool_name == "run_daily" and not _explicit_real_run(message):
        tool_name = "dry_run"
        args["dry_run"] = True
    for key in ("no_llm", "provider", "model", "base_url"):
        if key in defaults and key in allowed and key not in args:
            args[key] = defaults[key]
    return args


def _response_hint(tool_name: str) -> str:
    return {
        "web_search": "Web search results:",
        "search": "Local search results:",
        "rag_query": "RAG answer:",
        "rag_search": "RAG search results:",
        "rag_status": "RAG status:",
        "agent": "Agent loop completed:",
        "doctor": "Doctor report:",
        "tools": "Available tools:",
        "skills": "Skills:",
        "memory_show": "Agent memory:",
        "memory_remember": "Memory saved:",
        "memory_forget": "Memory updated:",
        "memory_review": "Memory review:",
        "history": "Recent runs:",
        "source_health": "Source health:",
        "feedback_list": "Feedback records:",
        "config_check": "Config check:",
        "dry_run": "Dry-run completed:",
        "run_daily": "Daily run completed:",
        "weekly": "Weekly run completed:",
        "external_cli": "External CLI tools:",
    }.get(tool_name, "")


def _looks_time_sensitive(message: str) -> bool:
    lowered = message.lower()
    markers = [
        "latest",
        "today",
        "breaking",
        "news",
        "\u521a\u521a",
        "\u6700\u65b0",
        "\u5b9e\u65f6",
        "\u4eca\u5929",
        "\u4eca\u65e5",
        "\u65b0\u95fb",
        "\u6d88\u606f",
        "\u5927\u4e8b",
        "\u52a8\u6001",
    ]
    return any(marker in lowered for marker in markers)


def _explicit_real_run(message: str) -> bool:
    lowered = message.lower()
    markers = [
        "write",
        "save",
        "run for real",
        "for real",
        "\u5199\u5165",
        "\u4fdd\u5b58",
        "\u771f\u5b9e\u8fd0\u884c",
        "\u6b63\u5f0f\u8fd0\u884c",
    ]
    return any(marker in lowered for marker in markers)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _int(value: Any, default: int, *, min_value: int, max_value: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(min_value, min(max_value, number))


def _float_range(value: Any, default: float, *, min_value: float, max_value: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = default
    return max(min_value, min(max_value, number))
