"""Tool registry for goldfish runtime actions."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .agent_kernel import AgentKernel, RunOptions
from .agent_memory import forget_memory, load_memory, memory_context, memory_path, remember_memory, review_memory
from .config_loader import load_config
from .external_cli import list_external_tools, run_external_tool
from .feedback_tracker import read_feedback_reports
from .notifier import feishu_status, send_feishu_test
from .providers.registry import resolve_llm_connection
from .rag_client import rag_query, rag_search, rag_status
from .search_engine import search_goldfish
from .skill_loader import list_skills, load_skill, skills_dir
from .state_store import GoldfishState
from .utils import agent_dir, get_env, kb_root
from .web_researcher import research_public_web, search_public_web


ToolHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    mutating: bool
    handler: ToolHandler
    allowed_paths: tuple[str, ...] = ()
    timeout_seconds: int | None = None


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
                "timeout_seconds": spec.timeout_seconds,
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
                timeout_seconds=180,
            )
        )
        self.register(
            ToolSpec(
                name="dry_run",
                description="Run the workflow without writing Obsidian files.",
                mutating=False,
                handler=_tool_dry_run,
                timeout_seconds=120,
            )
        )
        self.register(
            ToolSpec(
                name="weekly",
                description="Generate weekly AI trend report.",
                mutating=True,
                handler=_tool_weekly,
                allowed_paths=("04_Resources/AI-News/Weekly", "scripts/goldfish/output_cache"),
                timeout_seconds=180,
            )
        )
        self.register(ToolSpec(name="config_check", description="Validate and summarize config.", mutating=False, handler=_tool_config_check, timeout_seconds=20))
        self.register(ToolSpec(name="doctor", description="Diagnose runtime, config, keys, and writable paths.", mutating=False, handler=_tool_doctor, timeout_seconds=60))
        self.register(ToolSpec(name="memory_show", description="Show agent memory.", mutating=False, handler=_tool_memory_show, timeout_seconds=15))
        self.register(ToolSpec(name="memory_remember", description="Save a durable user-approved memory.", mutating=True, handler=_tool_memory_remember, timeout_seconds=15))
        self.register(ToolSpec(name="memory_forget", description="Forget matching durable memories.", mutating=True, handler=_tool_memory_forget, timeout_seconds=15))
        self.register(ToolSpec(name="memory_review", description="Review memory health and suggested updates.", mutating=False, handler=_tool_memory_review, timeout_seconds=20))
        self.register(ToolSpec(name="feedback_list", description="List checked feedback reports.", mutating=False, handler=_tool_feedback_list, timeout_seconds=20))
        self.register(ToolSpec(name="history", description="Show recent goldfish runs from SQLite state.", mutating=False, handler=_tool_history, timeout_seconds=20))
        self.register(ToolSpec(name="search", description="Search historical intelligence, insights, notes, and chat messages.", mutating=False, handler=_tool_search, timeout_seconds=30))
        self.register(ToolSpec(name="rag_query", description="Ask the configured local RAG knowledge base and return an answer with source chunks.", mutating=False, handler=_tool_rag_query, timeout_seconds=45))
        self.register(ToolSpec(name="rag_search", description="Search the configured local RAG knowledge base for matching source chunks.", mutating=False, handler=_tool_rag_search, timeout_seconds=45))
        self.register(ToolSpec(name="rag_status", description="Check local RAG service health, stats, and configuration.", mutating=False, handler=_tool_rag_status, timeout_seconds=20))
        self.register(ToolSpec(name="knowledge_lookup", description="Search local RAG first, then public web, and return two non-merged result blocks.", mutating=False, handler=_tool_knowledge_lookup, timeout_seconds=90))
        self.register(
            ToolSpec(
                name="web_search",
                description="Search the public web through the configured API/fallback provider; optionally fetch pages and save a research report.",
                mutating=True,
                handler=_tool_web_search,
                allowed_paths=("04_Resources/AI-News/Reports",),
                timeout_seconds=75,
            )
        )
        self.register(ToolSpec(name="skills", description="List or show lightweight goldfish skills.", mutating=False, handler=_tool_skills, timeout_seconds=10))
        self.register(ToolSpec(name="external_cli", description="List or run allow-listed external CLI tools.", mutating=True, handler=_tool_external_cli, timeout_seconds=60))
        self.register(ToolSpec(name="source_health", description="Show failing and high-value sources.", mutating=False, handler=_tool_source_health, timeout_seconds=30))
        self.register(ToolSpec(name="notify_status", description="Show configured notification channels and Feishu webhook status.", mutating=False, handler=_tool_notify_status, timeout_seconds=10))
        self.register(ToolSpec(name="notify_test", description="Send a test notification through the configured channel.", mutating=True, handler=_tool_notify_test, timeout_seconds=30))
        self.register(
            ToolSpec(
                name="agent",
                description="Run a bounded goal-driven agent loop over goldfish tools.",
                mutating=True,
                handler=_tool_agent_loop,
                allowed_paths=("scripts/goldfish/output_cache/tasks", "04_Resources/AI-News/Reports"),
                timeout_seconds=300,
            )
        )
        self.register(ToolSpec(name="tools", description="List available tools.", mutating=False, handler=lambda _: {"tools": self.list_tools()}, timeout_seconds=5))


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


def _tool_memory_show(payload: Dict[str, Any]) -> Dict[str, Any]:
    memory = load_memory(kb_root())
    result = {"path": str(memory_path(kb_root())), "memory": memory}
    if bool(payload.get("context", False)):
        result["context"] = memory_context(memory)
    return result


def _tool_memory_remember(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = str(payload.get("text") or payload.get("memory") or "").strip()
    kind = str(payload.get("kind") or "fact").strip()
    tags = payload.get("tags")
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if not isinstance(tags, list):
        tags = None
    return remember_memory(text, kind=kind, tags=tags, root=kb_root())


def _tool_memory_forget(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or payload.get("text") or "").strip()
    return forget_memory(query, root=kb_root())


def _tool_memory_review(_: Dict[str, Any]) -> Dict[str, Any]:
    return review_memory(kb_root())


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


def _tool_rag_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    question = str(payload.get("question") or payload.get("query") or "").strip()
    return rag_query(
        question,
        top_k=payload.get("top_k") or payload.get("limit"),
        retrieval_mode=payload.get("retrieval_mode"),
        category=str(payload.get("category") or "all"),
        use_llm=payload.get("use_llm"),
    )


def _tool_rag_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or payload.get("question") or "").strip()
    return rag_search(
        query,
        top_k=payload.get("top_k") or payload.get("limit"),
        retrieval_mode=payload.get("retrieval_mode"),
        category=str(payload.get("category") or "all"),
    )


def _tool_rag_status(_: Dict[str, Any]) -> Dict[str, Any]:
    return rag_status()


def _tool_knowledge_lookup(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or payload.get("question") or "").strip()
    if not query:
        return {"status": "error", "mode": "knowledge_lookup", "query": query, "error": "query is required", "error_type": "empty_query", "rag": {}, "web": {}}

    top_k = payload.get("top_k") or payload.get("rag_top_k") or payload.get("limit")
    web_limit = int(payload.get("web_limit", payload.get("limit", 5)) or 5)
    timeout = int(payload.get("timeout", 12) or 12)
    provider = payload.get("search_provider") or payload.get("provider")
    if not provider and _looks_time_sensitive_query(query):
        provider = "news"

    rag_result = rag_search(
        query,
        top_k=top_k,
        retrieval_mode=payload.get("retrieval_mode"),
        category=str(payload.get("category") or "all"),
    )
    try:
        web_results = search_public_web(query, limit=web_limit, timeout=timeout, provider=provider, timespan=payload.get("timespan"))
        web_result = {
            "status": "ok",
            "mode": "search",
            "query": query,
            "provider": web_results[0].get("source", "") if web_results else "",
            "provider_order": web_results[0].get("provider_order", "") if web_results else "",
            "count": len(web_results),
            "results": web_results,
            "safety": _public_web_safety(),
        }
    except Exception as exc:
        web_result = {
            "status": "error",
            "mode": "search",
            "query": query,
            "error": str(exc),
            "error_type": "web_search_failed",
            "count": 0,
            "results": [],
            "safety": _public_web_safety(),
        }

    return {
        "status": "ok" if rag_result.get("status") == "ok" or web_result.get("status") == "ok" else "error",
        "mode": "knowledge_lookup",
        "query": query,
        "strategy": ["rag_search", "web_search"],
        "conflict_policy": "RAG and web results are returned in separate blocks. Web results supplement but do not overwrite local RAG findings.",
        "rag": rag_result,
        "web": web_result,
        "safety": {
            "rag_first": True,
            "separate_blocks": True,
            "merged_claims": False,
            "api_keys_sent_to_rag": False,
            "public_web_only": True,
        },
    }


def _tool_web_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "") or "").strip()
    if not query:
        return {"status": "error", "query": query, "error": "query is required", "results": []}
    mode = str(payload.get("mode") or "search").strip().lower()
    limit = int(payload.get("limit", 8) or 8)
    timeout = int(payload.get("timeout", 12) or 12)
    provider = payload.get("search_provider") or payload.get("provider")
    if not provider and _looks_time_sensitive_query(query):
        provider = "news"
    timespan = payload.get("timespan") or payload.get("time_span")
    if mode in {"research", "report", "deep"} or bool(payload.get("fetch_pages", False)):
        return {
            "status": "ok",
            "mode": "research",
            "research": research_public_web(
                query=query,
                limit=limit,
                fetch_limit=int(payload.get("fetch_limit", 4) or 4),
                timeout=timeout,
                use_llm=not bool(payload.get("no_llm", False)),
                save=not bool(payload.get("no_save", False)),
                search_provider=provider,
                timespan=timespan,
                root=kb_root(),
            ),
            "safety": _public_web_safety(),
        }
    results = search_public_web(query, limit=limit, timeout=timeout, provider=provider, timespan=timespan)
    return {
        "status": "ok",
        "mode": "search",
        "query": query,
        "provider": results[0].get("source", "") if results else "",
        "provider_order": results[0].get("provider_order", "") if results else "",
        "count": len(results),
        "results": results,
        "safety": _public_web_safety(),
    }


def _public_web_safety() -> Dict[str, bool]:
    return {
        "public_web_only": True,
        "login": False,
        "cookies_saved": False,
        "anti_scraping_bypass": False,
    }


def _looks_time_sensitive_query(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in [
            "latest",
            "today",
            "breaking",
            "real-time",
            "realtime",
            "news",
            "刚刚",
            "最新",
            "实时",
            "今天",
            "新闻",
            "消息",
        ]
    )


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


def _tool_notify_status(_: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    return {
        "status": "ok",
        "notifications_enabled": bool(config.settings.get("enable_notifications", False)),
        "feishu": feishu_status(config.settings),
    }


def _tool_notify_test(payload: Dict[str, Any]) -> Dict[str, Any]:
    channel = str(payload.get("channel") or "feishu").strip().lower()
    if channel != "feishu":
        return {"status": "error", "error": f"unsupported notification channel: {channel}"}
    config = load_config()
    result = send_feishu_test(config.settings)
    return {"status": "ok" if result.get("sent") else "error", "channel": channel, "result": result}


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
            step_timeout=payload.get("step_timeout") or payload.get("step_timeout_seconds"),
            task_timeout=payload.get("task_timeout") or payload.get("task_timeout_seconds"),
            max_failures=payload.get("max_failures") or payload.get("max_total_failures"),
            max_consecutive_failures=payload.get("max_consecutive_failures"),
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
        "rag": rag_status(),
        "notifications": {
            "feishu": feishu_status(settings),
        },
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
        "tool_intents.json",
        "rag.json",
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
        "default": get_env("GOLDFISH_SEARCH_PROVIDER", "auto"),
        "tavily": {
            "configured": bool(get_env("TAVILY_API_KEY")),
            "endpoint": get_env("TAVILY_SEARCH_ENDPOINT", "https://api.tavily.com/search"),
        },
        "jina": {
            "configured": bool(get_env("JINA_API_KEY") or get_env("JINA_SEARCH_API_KEY")),
            "endpoint": get_env("JINA_SEARCH_ENDPOINT", "https://s.jina.ai/"),
        },
        "news": {"configured": True, "fallback": True, "notes": "Tavily/Jina when configured, then Hacker News Algolia, GDELT DOC, DuckDuckGo."},
        "hackernews": {"configured": True, "fallback": True, "endpoint": "https://hn.algolia.com/api/v1/search_by_date"},
        "gdelt": {"configured": True, "fallback": True, "endpoint": "https://api.gdeltproject.org/api/v2/doc/doc"},
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
