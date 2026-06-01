"""goldfish main entrypoint."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from modules.agent_kernel import AgentKernel, RunOptions
from modules.config_loader import ConfigError
from modules.conversation_agent import run_chat


CLI_COMMANDS = {
    "agent",
    "chat",
    "config",
    "doctor",
    "dry-run",
    "feedback",
    "history",
    "memory",
    "research",
    "run",
    "search",
    "setup",
    "skills",
    "sources",
    "tools",
    "weekly",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AI news reports for an Obsidian vault.")
    parser.add_argument("--date", help="Report date, e.g. 2026-05-26")
    parser.add_argument("--limit", type=int, help="Daily general item limit")
    parser.add_argument("--people-limit", type=int, help="People update limit")
    parser.add_argument("--paper-limit", type=int, help="Paper item limit")
    parser.add_argument("--github-limit", type=int, help="GitHub/open-source item limit")
    parser.add_argument("--product-limit", type=int, help="Product item limit")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing Obsidian files")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM and use rule-based summaries")
    parser.add_argument("--provider", help="LLM provider name, currently supports openai-compatible calls")
    parser.add_argument("--model", help="LLM model name, e.g. deepseek-v4-pro")
    parser.add_argument("--base-url", help="Optional OpenAI-compatible base URL")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report")
    parser.add_argument("--update-dashboard", action="store_true", help="Force dashboard update")
    parser.add_argument("--write-drafts", action="store_true", help="Write candidate knowledge draft notes")
    parser.add_argument("--draft-mode", choices=["off", "suggest", "ask", "auto"], help="Draft write mode")
    parser.add_argument("--verbose", action="store_true", help="Verbose logs")
    return parser.parse_args(argv)


def options_from_args(args: argparse.Namespace) -> RunOptions:
    return RunOptions(
        date=args.date,
        daily_limit=args.limit,
        people_limit=args.people_limit,
        paper_limit=args.paper_limit,
        github_limit=args.github_limit,
        product_limit=args.product_limit,
        dry_run=args.dry_run,
        no_llm=args.no_llm,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        weekly=args.weekly,
        update_dashboard=args.update_dashboard,
        write_drafts=args.write_drafts,
        draft_write_mode=args.draft_mode,
        verbose=args.verbose,
    )


def run_agent(argv: List[str] | None = None) -> Dict[str, Any]:
    return AgentKernel().run(options_from_args(parse_args(argv)))


def main() -> None:
    if len(sys.argv) == 1:
        raise SystemExit(run_chat())
    if sys.argv[1] in CLI_COMMANDS:
        from cli import main as cli_main

        raise SystemExit(cli_main(sys.argv[1:]))
    try:
        run_agent()
    except ConfigError as exc:
        print(f"[goldfish] 配置错误：{exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
