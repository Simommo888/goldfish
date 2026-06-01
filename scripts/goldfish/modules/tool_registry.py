"""Tool registry for goldfish runtime actions."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .agent_kernel import AgentKernel, RunOptions
from .agent_memory import load_memory, memory_path
from .config_loader import load_config
from .external_cli import list_external_tools, run_external_tool
from .feedback_tracker import read_feedback_reports
from .providers.registry import resolve_llm_connection
from .search_engine import search_goldfish
from .skill_loader import list_skills, load_skill, skills_dir
from .state_store import GoldfishState
from .utils import agent_dir, kb_root
from .web_researcher import research_public_web


ToolHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    mutating: bool
    handler: ToolHandler
    allowed_paths: tuple[str, ...] = ()


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "mutating": spec.mutating,
                "allowed_paths": list(spec.allowed_paths),
            }
            for spec in self.tools.values()
        ]

    def execute(self, name: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if name not in self.tools:
            raise KeyError(f"未知工具：{name}")
        spec = self.tools[name]
        payload = args or {}
        result = spec.handler(payload)
        result.setdefault("tool", name)
        result.setdefault("mutating", spec.mutating)
        return result

    def _register_defaults(self) -> None:
        self.register(
            ToolSpec(
                name="run_daily",
                description="Run the daily AI intelligence workflow.",
                mutating=True,
                handler=_tool_run_daily,
                allowed_paths=(
                    "04_Resources/AI-News",
                    "01_Dashboard/Home.md",
                    "05_Permanent-Notes/AI-Trends",
                    "11_Business-Ideas/AI-News-Inspirations",
                    "09_Prompts/AI-News",
                    "02_Projects/AI-News-Ideas",
                    "scripts/goldfish/output_cache",
                ),
            )
        )
        self.register(
            ToolSpec(
                name="dry_run",
                description="Run the workflow without writing Obsidian files.",
                mutating=False,
                handler=_tool_dry_run,
            )
        )
        self.register(
            ToolSpec(
                name="weekly",
                description="Generate weekly AI trend report.",
                mutating=True,
                handler=_tool_weekly,
                allowed_paths=("04_Resources/AI-News/Weekly", "scripts/goldfish/output_cache"),
            )
        )
        self.register(ToolSpec(name="config_check", description="Validate and summarize config.", mutating=False, handler=_tool_config_check))
        self.register(ToolSpec(name="doctor", description="Diagnose runtime, config, keys, and writable paths.", mutating=False, handler=_tool_doctor))
        self.register(ToolSpec(name="memory_show", description="Show agent memory.", mutating=False, handler=_tool_memory_show))
        self.register(ToolSpec(name="feedback_list", description="List checked feedback reports.", mutating=False, handler=_tool_feedback_list))
        self.register(ToolSpec(name="history", description="Show recent goldfish runs from SQLite state.", mutating=False, handler=_tool_history))
        self.register(ToolSpec(name="search", description="Search historical intelligence, insights, notes, and chat messages.", mutating=False, handler=_tool_search))
        self.register(ToolSpec(name="skills", description="List or show lightweight goldfish skills.", mutating=False, handler=_tool_skills))
        self.register(ToolSpec(name="external_cli", description="List or run allow-listed external CLI tools.", mutating=True, handler=_tool_external_cli))
        self.register(ToolSpec(name="source_health", description="Show failing and high-value sources.", mutating=False, handler=_tool_source_health))
        self.register(
            ToolSpec(
                name="research_web",
                description="Search the public web, fetch accessible pages, and save a Markdown research report.",
                mutating=True,
                handler=_tool_research_web,
                allowed_paths=("04_Resources/AI-News/Reports",),
            )
        )
        self.register(
            ToolSpec(
                name="agent",
                description="Run a bounded goal-driven agent loop over goldfish tools.",
                mutating=True,
                handler=_tool_agent_loop,
                allowed_paths=("scripts/goldfish/output_cache/tasks", "04_Resources/AI-News/Reports"),
            )
        )
        self.register(ToolSpec(name="tools", description="List available tools.", mutating=False, handler=lambda _: {"tools": self.list_tools()}))


def _options_from_payload(payload: Dict[str, Any], *, dry_run: bool = False, weekly: bool = False) -> RunOptions:
    return RunOptions(
        date=payload.get("date"),
        daily_limit=payload.get("daily_limit") or payload.get("limit"),
        people_limit=payload.get("people_limit"),
        paper_limit=payload.get("paper_limit"),
        github_limit=payload.get("github_limit"),
        product_limit=payload.get("product_limit"),
        dry_run=dry_run or bool(payload.get("dry_run", False)),
        no_llm=bool(payload.get("no_llm", False)),
        provider=payload.get("provider"),
        model=payload.get("model"),
        base_url=payload.get("base_url"),
        weekly=weekly or bool(payload.get("weekly", False)),
        update_dashboard=bool(payload.get("update_dashboard", False)),
        write_drafts=bool(payload.get("write_drafts", False)),
        draft_write_mode=payload.get("draft_mode") or payload.get("draft_write_mode"),
        verbose=bool(payload.get("verbose", False)),
        emit_report=bool(payload.get("emit_report", False)),
    )


def _tool_run_daily(payload: Dict[str, Any]) -> Dict[str, Any]:
    report = AgentKernel().run(_options_from_payload(payload))
    return {"status": "ok", "report": report}


def _tool_dry_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    options = _options_from_payload(payload, dry_run=True)
    options.emit_report = bool(payload.get("emit_report", False))
    report = AgentKernel().run(options)
    return {"status": "ok", "report": report}


def _tool_weekly(payload: Dict[str, Any]) -> Dict[str, Any]:
    options = _options_from_payload(payload, weekly=True)
    report = AgentKernel().run(options)
    return {"status": "ok", "report": report}


def _tool_config_check(_: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    return {
        "config_dir": str(config.config_dir),
        "sources_categories": sorted(config.sources.keys()),
        "people_count": len(config.people.get("people", [])),
        "keywords_loaded": bool(config.keywords.get("high_priority_keywords")),
        "settings_loaded": bool(config.settings),
        "agent_profile": config.agent_profile.get("name", ""),
    }


def _tool_memory_show(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"path": str(memory_path(kb_root())), "memory": load_memory(kb_root())}


def _tool_feedback_list(_: Dict[str, Any]) -> Dict[str, Any]:
    feedback = read_feedback_reports(kb_root())
    return {"feedback_count": len(feedback), "feedback": feedback}


def _tool_history(payload: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(payload.get("limit", 10) or 10)
    runs = GoldfishState(kb_root()).recent_runs(limit=limit)
    for run in runs:
        for key in ("counts_json", "paths_json"):
            if key in run:
                try:
                    run[key.replace("_json", "")] = json.loads(run[key])
                except Exception:
                    run[key.replace("_json", "")] = {}
                del run[key]
    return {"state_db": str(GoldfishState(kb_root()).path), "runs": runs}


def _tool_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "") or "").strip()
    if not query:
        return {"query": query, "count": 0, "results": [], "error": "query is required"}
    limit = int(payload.get("limit", 20) or 20)
    return search_goldfish(query, limit=limit, root=kb_root())


def _tool_skills(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "") or "").strip()
    if name:
        return {"skill": load_skill(name)}
    return {"skills_dir": str(skills_dir()), "skills": list_skills()}


def _tool_external_cli(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = str(payload.get("action") or "list").strip().lower()
    include_disabled = bool(payload.get("include_disabled", False))
    if action in {"list", "tools"}:
        return {"status": "ok", "external_tools": list_external_tools(include_disabled=include_disabled)}
    if action not in {"run", "exec", "execute"}:
        return {"status": "error", "error": f"unknown external_cli action: {action}"}
    name = str(payload.get("name") or payload.get("tool_name") or "").strip()
    if not name:
        return {"status": "error", "error": "external tool name is required"}
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    for key, value in payload.items():
        if key not in {"action", "name", "tool_name", "args", "cwd", "dry_run", "include_disabled"}:
            args[key] = value
    return run_external_tool(
        name,
        args=args,
        cwd=str(payload.get("cwd") or "."),
        dry_run=bool(payload.get("dry_run", False)),
    )


def _tool_source_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(payload.get("limit", 8) or 8)
    state = GoldfishState(kb_root())
    return {
        "state_db": str(state.path),
        "summary": state.source_health_summary(limit=limit),
        "recent": state.recent_source_health(limit=limit),
    }


def _tool_research_web(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "") or "").strip()
    if not query:
        return {"query": query, "error": "query is required", "status": "error"}
    return {
        "status": "ok",
        "research": research_public_web(
            query=query,
            limit=int(payload.get("limit", 6) or 6),
            fetch_limit=int(payload.get("fetch_limit", 4) or 4),
            timeout=int(payload.get("timeout", 12) or 12),
            use_llm=not bool(payload.get("no_llm", False)),
            save=not bool(payload.get("no_save", False)),
            search_provider=payload.get("search_provider") or payload.get("provider"),
            root=kb_root(),
        ),
    }


def _tool_agent_loop(payload: Dict[str, Any]) -> Dict[str, Any]:
    goal = str(payload.get("goal") or payload.get("query") or "").strip()
    if not goal:
        return {"status": "error", "error": "goal is required"}
    from .agent_loop import run_agent_loop

    return {
        "status": "ok",
        "agent": run_agent_loop(
            goal,
            registry=DEFAULT_REGISTRY,
            max_steps=int(payload.get("max_steps", 5) or 5),
            no_llm=bool(payload.get("no_llm", False)),
            no_save=bool(payload.get("no_save", False)),
            root=kb_root(),
        ),
    }


def _tool_doctor(_: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    settings = config.settings
    connection = resolve_llm_connection(settings)
    root = kb_root()
    state = GoldfishState(root)
    last_run = state.last_run()
    source_summary = state.source_health_summary()
    writable_checks = {
        "ai_news": _can_write(root / "04_Resources" / "AI-News"),
        "output_cache": _can_write(root / "scripts" / "goldfish" / "output_cache"),
        "draft_permanent_notes": _can_write(root / "05_Permanent-Notes" / "AI-Trends"),
        "draft_business": _can_write(root / "11_Business-Ideas" / "AI-News-Inspirations"),
        "draft_prompts": _can_write(root / "09_Prompts" / "AI-News"),
        "draft_projects": _can_write(root / "02_Projects" / "AI-News-Ideas"),
    }
    try:
        import openai  # type: ignore  # noqa: F401

        openai_package = True
    except Exception:
        openai_package = False
    deepseek_connectivity = _check_deepseek_connectivity(connection)
    return {
        "kb_root": str(root),
        "agent_dir": str(agent_dir()),
        "state_db": str(state.path),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "goldfish_package": _package_status(),
        "required_packages": _required_package_status(),
        "config_ok": bool(settings and config.sources and config.keywords),
        "config_files": _config_file_status(),
        "obsidian_dirs": _obsidian_dir_status(root),
        "github_actions": _github_actions_status(root),
        "skills": {
            "skills_dir": str(skills_dir()),
            "count": len(list_skills()),
            "names": [skill["name"] for skill in list_skills()],
        },
        "external_cli": {
            "count": len(list_external_tools()),
            "names": [tool["name"] for tool in list_external_tools()],
        },
        "search_providers": _search_provider_status(),
        "provider": connection["provider"],
        "model": connection["model"],
        "base_url": connection["base_url"] or "default",
        "has_model_api_key": bool(connection["api_key"]),
        "deepseek_api": deepseek_connectivity,
        "openai_package": openai_package,
        "writable": writable_checks,
        "auto_create_knowledge_drafts": settings.get("auto_create_knowledge_drafts"),
        "draft_write_mode": settings.get("draft_write_mode", "suggest"),
        "last_run": _decode_run(last_run) if last_run else None,
        "source_health": source_summary,
    }


def _can_write(path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".goldfish_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _package_status() -> Dict[str, Any]:
    try:
        from importlib.metadata import version

        return {"installed": True, "version": version("goldfish")}
    except Exception as exc:
        return {"installed": False, "error": str(exc)}


def _required_package_status() -> Dict[str, Dict[str, Any]]:
    try:
        from importlib.metadata import version
    except Exception as exc:
        return {"importlib.metadata": {"installed": False, "error": str(exc)}}

    packages = {
        "requests": "requests",
        "feedparser": "feedparser",
        "openai": "openai",
        "rich": "rich",
        "Pillow": "Pillow",
    }
    statuses: Dict[str, Dict[str, Any]] = {}
    for display_name, distribution_name in packages.items():
        try:
            statuses[display_name] = {"installed": True, "version": version(distribution_name)}
        except Exception as exc:
            statuses[display_name] = {"installed": False, "error": str(exc)}
    return statuses


def _config_file_status() -> Dict[str, bool]:
    config_dir = agent_dir() / "config"
    names = [
        "sources.json",
        "people.json",
        "keywords.json",
        "settings.json",
        "llm_prompts.json",
        "agent_profile.json",
        "external_tools.json",
        "search_providers.json",
    ]
    status: Dict[str, bool] = {}
    for name in names:
        path = config_dir / name
        if not path.exists():
            status[name] = False
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            status[name] = True
        except Exception:
            status[name] = False
    return status


def _search_provider_status() -> Dict[str, Any]:
    return {
        "default": os.environ.get("GOLDFISH_SEARCH_PROVIDER", "auto"),
        "bing": {
            "configured": bool(os.environ.get("BING_SEARCH_API_KEY") or os.environ.get("AZURE_BING_SEARCH_KEY")),
            "endpoint": os.environ.get("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"),
        },
        "google": {
            "configured": bool(
                (os.environ.get("GOOGLE_SEARCH_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
                and (os.environ.get("GOOGLE_SEARCH_CX") or os.environ.get("GOOGLE_CSE_ID"))
            ),
        },
        "duckduckgo": {"configured": True, "fallback": True},
    }


def _obsidian_dir_status(root) -> Dict[str, bool]:
    dirs = [
        "04_Resources/AI-News/Daily",
        "04_Resources/AI-News/Weekly",
        "04_Resources/AI-News/People-Watch",
        "04_Resources/AI-News/Raw",
        "04_Resources/AI-News/Reports",
        "01_Dashboard",
    ]
    return {path: (root / path).exists() for path in dirs}


def _github_actions_status(root) -> Dict[str, Any]:
    workflow = root / ".github" / "workflows" / "goldfish.yml"
    if not workflow.exists():
        return {"exists": False}
    text = workflow.read_text(encoding="utf-8")
    return {
        "exists": True,
        "uses_deepseek_secret": "DEEPSEEK_API_KEY" in text,
        "uses_goldfish_cli": "goldfish run" in text,
        "commits_reports": "chore: update daily AI news report" in text,
        "commits_drafts": "05_Permanent-Notes/AI-Trends" in text and "11_Business-Ideas/AI-News-Inspirations" in text,
    }


def _check_deepseek_connectivity(connection: Dict[str, str]) -> Dict[str, Any]:
    if connection["provider"] != "deepseek":
        return {"checked": False, "reason": "provider is not deepseek"}
    if not connection["api_key"]:
        return {"checked": False, "ok": False, "reason": "missing DEEPSEEK_API_KEY"}
    try:
        from .providers.registry import get_provider

        text = get_provider(
            {
                "llm_provider": "deepseek",
                "llm_model": connection["model"],
                "llm_base_url": connection["base_url"],
            }
        ).generate_text(
            [
                {"role": "system", "content": "Return only OK."},
                {"role": "user", "content": "ping"},
            ],
            temperature=0,
        )
        return {"checked": True, "ok": bool(text.strip()), "response_preview": text.strip()[:40]}
    except Exception as exc:
        return {"checked": True, "ok": False, "error": str(exc)}


def _decode_run(run: Dict[str, Any]) -> Dict[str, Any]:
    decoded = dict(run)
    for key in ("counts_json", "paths_json"):
        if key in decoded:
            try:
                decoded[key.replace("_json", "")] = json.loads(decoded[key])
            except Exception:
                decoded[key.replace("_json", "")] = {}
            del decoded[key]
    return decoded


DEFAULT_REGISTRY = ToolRegistry()
