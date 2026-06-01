"""Command-line interface for the goldfish agent."""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from modules.conversation_agent import run_chat
from modules.doctor_view import print_doctor_report
from modules.setup_agent import run_setup
from modules.tool_registry import DEFAULT_REGISTRY


COMMON_RUN_ARGS = [
    ("--date", {"help": "Report date, e.g. 2026-05-31"}),
    ("--limit", {"type": int, "help": "Daily general item limit"}),
    ("--people-limit", {"type": int, "help": "People update limit"}),
    ("--paper-limit", {"type": int, "help": "Paper item limit"}),
    ("--github-limit", {"type": int, "help": "GitHub/open-source item limit"}),
    ("--product-limit", {"type": int, "help": "Product item limit"}),
    ("--no-llm", {"action": "store_true", "help": "Disable LLM and use rule summaries"}),
    ("--provider", {"help": "LLM provider; deepseek/openai/openai-compatible"}),
    ("--model", {"help": "LLM model name"}),
    ("--base-url", {"help": "Optional OpenAI-compatible base URL"}),
    ("--weekly", {"action": "store_true", "help": "Generate weekly report"}),
    ("--update-dashboard", {"action": "store_true", "help": "Force dashboard update"}),
    ("--write-drafts", {"action": "store_true", "help": "Write candidate knowledge draft notes"}),
    ("--draft-mode", {"choices": ["off", "suggest", "ask", "auto"], "help": "Draft write mode"}),
    ("--verbose", {"action": "store_true", "help": "Verbose logs"}),
]


def _add_run_args(parser: argparse.ArgumentParser, include_dry_run: bool = True) -> None:
    for flag, kwargs in COMMON_RUN_ARGS:
        parser.add_argument(flag, **kwargs)
    if include_dry_run:
        parser.add_argument("--dry-run", action="store_true", help="Run without writing Obsidian files")


def _namespace_to_payload(namespace: argparse.Namespace, force: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = dict(force or {})
    for key, value in vars(namespace).items():
        if key in {"command", "subcommand", "func"} or value is None or value is False:
            continue
        payload[key] = value
    return payload


def _print_json(payload: Dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_run(namespace: argparse.Namespace) -> int:
    payload = _namespace_to_payload(namespace)
    return _print_json(DEFAULT_REGISTRY.execute("run_daily", payload))


def command_dry_run(namespace: argparse.Namespace) -> int:
    payload = _namespace_to_payload(namespace, {"dry_run": True})
    return _print_json(DEFAULT_REGISTRY.execute("dry_run", payload))


def command_weekly(namespace: argparse.Namespace) -> int:
    payload = _namespace_to_payload(namespace, {"weekly": True})
    return _print_json(DEFAULT_REGISTRY.execute("weekly", payload))


def command_tool(name: str, namespace: argparse.Namespace) -> int:
    return _print_json(DEFAULT_REGISTRY.execute(name, _namespace_to_payload(namespace)))


def command_doctor(namespace: argparse.Namespace) -> int:
    report = DEFAULT_REGISTRY.execute("doctor", _namespace_to_payload(namespace))
    if getattr(namespace, "json", False):
        return _print_json(report)
    print_doctor_report(report)
    return 0


def command_agent(namespace: argparse.Namespace) -> int:
    payload = _namespace_to_payload(namespace)
    payload["goal"] = namespace.goal
    return _print_json(DEFAULT_REGISTRY.execute("agent", payload))


def command_external(namespace: argparse.Namespace) -> int:
    payload = _namespace_to_payload(namespace)
    if namespace.external_action == "list":
        payload["action"] = "list"
    else:
        args = dict(_parse_cli_key_values(namespace.args or []))
        payload = {
            "action": "run",
            "name": namespace.name,
            "args": args,
            "cwd": namespace.cwd,
            "dry_run": namespace.dry_run,
        }
    return _print_json(DEFAULT_REGISTRY.execute("external_cli", payload))


def command_chat(namespace: argparse.Namespace) -> int:
    return run_chat(
        once=namespace.once,
        use_llm=not namespace.no_llm,
        provider=namespace.provider,
        model=namespace.model,
        base_url=namespace.base_url,
    )


def command_setup(namespace: argparse.Namespace) -> int:
    return run_setup(once=namespace.once)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goldfish",
        description="goldfish - AI intelligence and knowledge deposition agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the daily agent")
    _add_run_args(run_parser)
    run_parser.set_defaults(func=command_run)

    dry_parser = subparsers.add_parser("dry-run", help="Run without writing files")
    _add_run_args(dry_parser, include_dry_run=False)
    dry_parser.set_defaults(func=command_dry_run)

    weekly_parser = subparsers.add_parser("weekly", help="Generate weekly report")
    _add_run_args(weekly_parser, include_dry_run=True)
    weekly_parser.set_defaults(func=command_weekly)

    config_parser = subparsers.add_parser("config", help="Config commands")
    config_sub = config_parser.add_subparsers(dest="subcommand", required=True)
    config_check = config_sub.add_parser("check", help="Validate and summarize config")
    config_check.set_defaults(func=lambda ns: command_tool("config_check", ns))

    memory_parser = subparsers.add_parser("memory", help="Memory commands")
    memory_sub = memory_parser.add_subparsers(dest="subcommand", required=True)
    memory_show = memory_sub.add_parser("show", help="Show agent memory")
    memory_show.set_defaults(func=lambda ns: command_tool("memory_show", ns))

    feedback_parser = subparsers.add_parser("feedback", help="Feedback commands")
    feedback_sub = feedback_parser.add_subparsers(dest="subcommand", required=True)
    feedback_list = feedback_sub.add_parser("list", help="List checked feedback reports")
    feedback_list.set_defaults(func=lambda ns: command_tool("feedback_list", ns))

    history_parser = subparsers.add_parser("history", help="Show recent runs")
    history_parser.add_argument("--limit", type=int, default=10, help="How many runs to show")
    history_parser.set_defaults(func=lambda ns: command_tool("history", ns))

    search_parser = subparsers.add_parser("search", help="Search historical intelligence")
    search_parser.add_argument("query", help="Search query, e.g. MCP or AI Coding commercialization")
    search_parser.add_argument("--limit", type=int, default=20, help="How many results to show")
    search_parser.set_defaults(func=lambda ns: command_tool("search", ns))

    research_parser = subparsers.add_parser("research", help="Search public web and save a research report")
    research_parser.add_argument("query", help="Research query")
    research_parser.add_argument("--limit", type=int, default=6, help="How many search results to collect")
    research_parser.add_argument("--fetch-limit", type=int, default=4, help="How many result pages to fetch")
    research_parser.add_argument("--timeout", type=int, default=12, help="Network timeout in seconds")
    research_parser.add_argument("--no-llm", action="store_true", help="Disable LLM synthesis")
    research_parser.add_argument("--no-save", action="store_true", help="Do not save Markdown report")
    research_parser.set_defaults(func=lambda ns: command_tool("research_web", ns))

    agent_parser = subparsers.add_parser("agent", help="Run a bounded goal-driven agent loop")
    agent_parser.add_argument("goal", help="Natural-language goal for goldfish")
    agent_parser.add_argument("--no-llm", action="store_true", help="Disable LLM planning/final summary")
    agent_parser.add_argument("--max-steps", type=int, default=5, help="Maximum agent steps, 1-8")
    agent_parser.add_argument("--no-save", action="store_true", help="Do not let delegated tools save optional reports")
    agent_parser.set_defaults(func=command_agent)

    tools_parser = subparsers.add_parser("tools", help="List available local tools")
    tools_parser.set_defaults(func=lambda ns: command_tool("tools", ns))

    external_parser = subparsers.add_parser("external", help="List or run allow-listed external CLI tools")
    external_sub = external_parser.add_subparsers(dest="external_action", required=True)
    external_list = external_sub.add_parser("list", help="List configured external CLI tools")
    external_list.add_argument("--include-disabled", action="store_true", help="Show disabled examples too")
    external_list.set_defaults(func=command_external)
    external_run = external_sub.add_parser("run", help="Run a configured external CLI tool")
    external_run.add_argument("name", help="External tool name, e.g. rg_search")
    external_run.add_argument("args", nargs="*", help="Tool args as key=value, e.g. query=MCP path=scripts")
    external_run.add_argument("--cwd", default=".", help="Working directory relative to project root")
    external_run.add_argument("--dry-run", action="store_true", help="Show command without executing")
    external_run.set_defaults(func=command_external)

    skills_parser = subparsers.add_parser("skills", help="List or show goldfish skills")
    skills_parser.add_argument("name", nargs="?", help="Optional skill name")
    skills_parser.set_defaults(func=lambda ns: command_tool("skills", ns))

    source_parser = subparsers.add_parser("sources", help="Source maintenance commands")
    source_sub = source_parser.add_subparsers(dest="subcommand", required=True)
    source_health = source_sub.add_parser("health", help="Show source health summary")
    source_health.add_argument("--limit", type=int, default=8, help="How many source records to show")
    source_health.set_defaults(func=lambda ns: command_tool("source_health", ns))

    doctor_parser = subparsers.add_parser("doctor", help="Check local runtime and config")
    doctor_parser.add_argument("--json", action="store_true", help="Print the raw structured doctor report")
    doctor_parser.set_defaults(func=command_doctor)

    chat_parser = subparsers.add_parser("chat", help="Start a conversational Agent session")
    chat_parser.add_argument("--once", help="Send one message and exit, useful for scripts/tests")
    chat_parser.add_argument("--no-llm", action="store_true", help="Disable LLM fallback in chat")
    chat_parser.add_argument("--provider", help="LLM provider for chat fallback and runs")
    chat_parser.add_argument("--model", help="LLM model for chat fallback and runs")
    chat_parser.add_argument("--base-url", help="OpenAI-compatible base URL")
    chat_parser.set_defaults(func=command_chat)

    setup_parser = subparsers.add_parser("setup", help="Configure goldfish model and local environment")
    setup_parser.add_argument("--once", help="Run one setup command, e.g. '/model list'")
    setup_parser.set_defaults(func=command_setup)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    namespace = parser.parse_args(argv)
    if not hasattr(namespace, "func"):
        return run_chat()
    return int(namespace.func(namespace))


def _parse_cli_key_values(parts: List[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    positional: List[str] = []
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            if key:
                values[key.replace("-", "_")] = value
            continue
        positional.append(part)
    if positional:
        values["query"] = " ".join(positional)
    return values


if __name__ == "__main__":
    raise SystemExit(main())
