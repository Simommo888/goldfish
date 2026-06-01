"""Natural-language and slash-command routing for goldfish chat."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any, Dict

from .tool_registry import DEFAULT_REGISTRY, ToolRegistry


@dataclass(frozen=True)
class RoutedCommand:
    tool_name: str
    args: Dict[str, Any]
    response_hint: str = ""
    exit_requested: bool = False
    unknown: bool = False


class CommandRouter:
    """Route chat text into goldfish's explicit local tool surface.

    This is intentionally narrower than a shell. goldfish can run its own
    workflow tools, inspect state, search public web pages through the bounded
    research tool, and answer usage questions; it does not execute arbitrary
    user-provided commands.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or DEFAULT_REGISTRY

    def route(self, message: str, session_defaults: Dict[str, Any] | None = None) -> RoutedCommand:
        session_defaults = session_defaults or {}
        text = message.strip()
        lower = text.lower()
        if lower in {"exit", "quit", "q", "/exit", "/quit", "bye", "goodbye"}:
            return RoutedCommand("", {}, exit_requested=True)
        if lower in {"help", "/help"}:
            return RoutedCommand("help", {}, "help")
        if lower.startswith("/"):
            return self._route_slash(text, session_defaults)
        return self._route_natural(text, session_defaults)

    def execute(self, routed: RoutedCommand) -> str:
        if routed.exit_requested:
            return "__EXIT__"
        if routed.tool_name == "help":
            return HELP_TEXT
        if routed.unknown:
            return ""
        result = self.registry.execute(routed.tool_name, routed.args)
        body = json.dumps(result, ensure_ascii=False, indent=2)
        return f"{routed.response_hint}\n{body}" if routed.response_hint else body

    def _route_slash(self, text: str, defaults: Dict[str, Any]) -> RoutedCommand:
        parts = shlex.split(text, posix=False)
        command = parts[0].lower()
        rest = parts[1:]
        args = dict(defaults)

        if command in {"/run", "/daily"}:
            args.update(_parse_flags(rest))
            return RoutedCommand("run_daily", args, "Daily run completed:")
        if command in {"/dry", "/dry-run", "/test"}:
            args.update(_parse_flags(rest))
            return RoutedCommand("dry_run", args, "Dry-run completed:")
        if command == "/weekly":
            args.update(_parse_flags(rest))
            return RoutedCommand("weekly", args, "Weekly run completed:")
        if command == "/config":
            return RoutedCommand("config_check", {}, "Config check:")
        if command == "/doctor":
            return RoutedCommand("doctor", {}, "Doctor report:")
        if command == "/memory":
            return RoutedCommand("memory_show", {}, "Agent memory:")
        if command == "/feedback":
            return RoutedCommand("feedback_list", {}, "Feedback records:")
        if command == "/history":
            args.update(_parse_flags(rest))
            return RoutedCommand("history", args, "Recent runs:")
        if command == "/search":
            parsed = _parse_flags(rest)
            query_parts = _positional_parts(rest)
            parsed.setdefault("query", " ".join(query_parts).strip())
            return RoutedCommand("search", parsed, "Local search results:")
        if command == "/research":
            parsed = _parse_flags(rest)
            query_parts = _positional_parts(rest)
            parsed.setdefault("query", " ".join(query_parts).strip())
            return RoutedCommand("research_web", parsed, "Web research completed:")
        if command == "/agent":
            parsed = _parse_flags(rest)
            goal_parts = _positional_parts(rest)
            parsed.setdefault("goal", " ".join(goal_parts).strip())
            return RoutedCommand("agent", parsed, "Agent loop completed:")
        if command == "/skills":
            parsed = _parse_flags(rest)
            name_parts = _positional_parts(rest)
            if name_parts:
                parsed["name"] = name_parts[0]
            return RoutedCommand("skills", parsed, "Skills:")
        if command in {"/source-health", "/sources"}:
            parsed = _parse_flags(rest)
            return RoutedCommand("source_health", parsed, "Source health:")
        if command == "/tools":
            return RoutedCommand("tools", {}, "Available tools:")
        if command in {"/external", "/exec"}:
            parsed = _parse_flags(rest)
            positional = _positional_parts(rest)
            if not positional:
                return RoutedCommand("external_cli", {"action": "list"}, "External CLI tools:")
            name = positional[0]
            args = _parse_key_values(positional[1:])
            args.update(parsed)
            return RoutedCommand("external_cli", {"action": "run", "name": name, "args": args}, "External CLI result:")
        return RoutedCommand("", {}, f"Unknown command: {command}", unknown=True)

    def _route_natural(self, text: str, defaults: Dict[str, Any]) -> RoutedCommand:
        args = dict(defaults)
        lowered = text.lower()
        wants_dry_run = any(word in lowered for word in ["dry-run", "dry run", "test run"])
        wants_weekly = "weekly" in lowered
        wants_report = any(word in lowered for word in ["daily", "briefing", "report", "run"])
        wants_drafts = any(word in lowered for word in ["draft", "drafts"])

        if "config check" in lowered:
            return RoutedCommand("config_check", {}, "Config check:")
        if "doctor" in lowered:
            return RoutedCommand("doctor", {}, "Doctor report:")
        if "memory" in lowered:
            return RoutedCommand("memory_show", {}, "Agent memory:")
        if "feedback" in lowered:
            return RoutedCommand("feedback_list", {}, "Feedback records:")
        if "history" in lowered:
            return RoutedCommand("history", {}, "Recent runs:")
        if any(
            word in lowered
            for word in [
                "research",
                "investigate",
                "study",
                "market",
                "opportunity",
                "trend",
                "mcp",
                "rag",
                "ai coding",
                "business idea",
                "startup",
                "mvp",
                "pricing",
                "monetization",
                "prompt",
                "permanent note",
                "draft",
                "source quality",
                "fact check",
                "knowledge base",
                "skill",
                "研究",
                "商业机会",
                "趋势",
                "商业想法",
                "创业",
                "变现",
                "永久笔记",
                "提示词",
                "草稿",
                "知识库",
                "沉淀",
                "信源",
                "来源",
                "核验",
            ]
        ):
            return RoutedCommand("agent", {**args, "goal": text}, "Agent loop completed:")
        if "search" in lowered:
            query = text.replace("search", "", 1).strip()
            return RoutedCommand("search", {"query": query}, "Local search results:")
        if "skills" in lowered:
            return RoutedCommand("skills", {}, "Skills:")
        if any(word in lowered for word in ["source health", "sources health"]):
            return RoutedCommand("source_health", {}, "Source health:")
        if "tools" in lowered:
            return RoutedCommand("tools", {}, "Available tools:")
        if any(word in lowered for word in ["external cli", "external tools", "cli tools"]):
            return RoutedCommand("external_cli", {"action": "list"}, "External CLI tools:")
        if wants_weekly:
            return RoutedCommand("weekly", args, "Weekly run completed:")
        if wants_dry_run:
            return RoutedCommand("dry_run", args, "Dry-run completed:")
        if wants_report:
            if wants_drafts:
                args["write_drafts"] = True
            return RoutedCommand("run_daily", args, "Daily run completed:")
        return RoutedCommand("", {}, "", unknown=True)


def _parse_flags(parts: list[str]) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    idx = 0
    while idx < len(parts):
        part = parts[idx]
        if not part.startswith("--"):
            idx += 1
            continue
        key = part[2:].replace("-", "_")
        if idx + 1 >= len(parts) or parts[idx + 1].startswith("--"):
            args[key] = True
            idx += 1
        else:
            args[key] = _coerce(parts[idx + 1])
            idx += 2
    return args


def _coerce(value: str) -> Any:
    cleaned = value.strip('"')
    if cleaned.lower() in {"true", "false"}:
        return cleaned.lower() == "true"
    try:
        return int(cleaned)
    except ValueError:
        return cleaned


def _positional_parts(parts: list[str]) -> list[str]:
    values: list[str] = []
    skip_next = False
    for index, part in enumerate(parts):
        if skip_next:
            skip_next = False
            continue
        if part.startswith("--"):
            if index + 1 < len(parts) and not parts[index + 1].startswith("--"):
                skip_next = True
            continue
        values.append(part.strip('"'))
    return values


def _parse_key_values(parts: list[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    rest: list[str] = []
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            if key:
                values[key.replace("-", "_")] = _coerce(value)
            continue
        rest.append(part)
    if rest:
        values["query"] = " ".join(rest).strip()
    return values


HELP_TEXT = """goldfish commands:

/run                Generate the daily AI intelligence report
/dry                Dry-run without writing Obsidian files
/weekly             Generate the weekly trend report
/config             Validate configuration
/doctor             Diagnose Python, package, model, config, paths, sources, and Actions
/memory             Show agent memory
/feedback           Show feedback records
/history            Show recent runs
/search <query>     Search local goldfish history and generated notes
/research <query>   Search the public web, fetch accessible pages, and save a report
/agent <goal>       Plan and run a bounded goal-driven agent loop
/skills [name]      List or open lightweight skills
/source-health      Show source health
/tools              List available local tools
/external           List allow-listed external CLI tools
/exec <tool> k=v    Run an allow-listed external CLI tool
/model              Point you to `goldfish setup` for model/API key configuration
/language [code]    Show or switch output language
/provider <name>    Switch provider for this chat session
/base-url <url>     Switch base URL for this chat session
/llm                Enable LLM replies for this chat session
/no-llm             Disable LLM replies for this chat session
exit                End the session
"""
