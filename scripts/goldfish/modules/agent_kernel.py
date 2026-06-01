"""Core runtime for goldfish.

CLI, chat, scheduled jobs, and future gateways should call AgentKernel instead
of duplicating workflow logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from .agent_memory import apply_memory_preferences, load_memory, save_memory, update_memory_from_run
from .classifier import classify_items
from .config_loader import enabled_people, load_config, sources_by_category
from .dashboard_updater import update_home_dashboard
from .deduplicator import deduplicate_items
from .feedback_tracker import write_feedback_report
from .github_trending_fetcher import fetch_github_trending
from .insight_extractor import extract_insights
from .knowledge_suggester import write_draft_notes, write_knowledge_report
from .llm_summarizer import summarize_items
from .notifier import notify
from .obsidian_writer import write_daily_outputs, write_weekly_output
from .paper_fetcher import fetch_papers
from .people_watcher import watch_people
from .product_fetcher import fetch_products
from .report_generator import generate_daily_report, generate_people_report
from .rss_fetcher import fetch_rss_sources
from .scorer import score_items
from .source_health import build_source_health_records
from .state_store import GoldfishState
from .storage import read_recent_daily_reports
from .utils import is_weekend, kb_root, log, today_string, week_string
from .web_fetcher import build_manual_review_items
from .weekly_report_generator import generate_weekly_report


@dataclass
class RunOptions:
    date: str | None = None
    daily_limit: int | None = None
    people_limit: int | None = None
    paper_limit: int | None = None
    github_limit: int | None = None
    product_limit: int | None = None
    dry_run: bool = False
    no_llm: bool = False
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    weekly: bool = False
    update_dashboard: bool = False
    write_drafts: bool = False
    draft_write_mode: str | None = None
    verbose: bool = False
    emit_report: bool = True


class AgentKernel:
    def __init__(self) -> None:
        self.root = kb_root()

    def run(self, options: RunOptions | None = None) -> Dict[str, Any]:
        options = options or RunOptions()
        config = load_config()
        settings = dict(config.settings)
        if options.provider:
            settings["llm_provider"] = options.provider
        if options.model:
            settings["llm_model"] = options.model
        if options.base_url:
            settings["llm_base_url"] = options.base_url

        timezone_name = settings.get("timezone", "Asia/Shanghai")
        date_text = options.date or today_string(timezone_name)
        dry_run = options.dry_run or bool(settings.get("dry_run_default", False))
        use_llm = not options.no_llm and bool(settings.get("use_llm", True))
        allow_network = (not dry_run) or bool(settings.get("fetch_network_in_dry_run", False))
        timeout = int(settings.get("network_timeout_seconds", 10))
        enable_memory = bool(settings.get("enable_agent_memory", True))
        memory = load_memory(self.root) if enable_memory else {}

        limits = {
            "daily_limit": int(options.daily_limit or settings.get("daily_limit") or 10),
            "people_limit": int(options.people_limit or settings.get("people_limit") or 5),
            "paper_limit": int(options.paper_limit or settings.get("paper_limit") or 5),
            "github_limit": int(options.github_limit or settings.get("github_limit") or 5),
            "product_limit": int(options.product_limit or settings.get("product_limit") or 5),
        }

        log(f"date={date_text}, dry_run={dry_run}, allow_network={allow_network}, use_llm={use_llm}", options.verbose)

        official_sources = sources_by_category(config.sources, "official")
        research_sources = sources_by_category(config.sources, "research")
        open_source_sources = sources_by_category(config.sources, "open_source")
        product_sources = sources_by_category(config.sources, "product")
        configured_sources = official_sources + research_sources + open_source_sources + product_sources

        official_rss = [source for source in official_sources if source.get("rss_url")]
        official_manual = [source for source in official_sources if not source.get("rss_url")]

        items: List[Dict[str, Any]] = []
        items.extend(fetch_rss_sources(official_rss, limit_per_source=2, timeout=timeout, allow_network=allow_network))
        items.extend(build_manual_review_items(official_manual))
        items.extend(fetch_papers(research_sources, limit=limits["paper_limit"], timeout=timeout, allow_network=allow_network))
        items.extend(fetch_github_trending(open_source_sources, limit=limits["github_limit"], timeout=timeout, allow_network=allow_network))
        non_github_open_source = [source for source in open_source_sources if "github" not in source.get("name", "").lower()]
        items.extend(build_manual_review_items(non_github_open_source))
        items.extend(fetch_products(product_sources, limit=limits["product_limit"], allow_network=allow_network))
        items.extend(watch_people(enabled_people(config.people), limit_per_source=1, timeout=timeout, allow_network=allow_network))

        if not items:
            items.append(
                {
                    "title": "今日暂无高质量自动抓取内容",
                    "url": "",
                    "source_name": "goldfish",
                    "source_category": "system",
                    "summary": "请检查 sources.json 或人工查看待查看来源。",
                    "raw_content": "",
                    "published": "",
                    "content_type": "system",
                    "needs_manual_review": True,
                }
            )

        classify_items(items, config.keywords)
        score_items(items, config.keywords, timezone_name)
        source_health = build_source_health_records(configured_sources, items, timezone_name)
        if enable_memory:
            apply_memory_preferences(items, memory)
        deduped = deduplicate_items(items)
        selected = _select_report_items(deduped, **limits)
        report_items = summarize_items(selected["items"], settings, config.llm_prompts, use_llm=use_llm)
        people_items = summarize_items(selected["people"], settings, config.llm_prompts, use_llm=use_llm)
        insight_limit = int(settings.get("knowledge_report_limit", 8))
        insight_min_score = float(settings.get("knowledge_min_score", 5))
        insights = extract_insights(report_items, memory, limit=insight_limit, min_score=insight_min_score)

        daily_markdown = generate_daily_report(date_text, report_items, people_items)
        people_markdown = generate_people_report(date_text, people_items)

        raw_payload = {
            "date": date_text,
            "settings": {key: settings.get(key) for key in sorted(settings.keys()) if "key" not in key.lower()},
            "counts": {
                "fetched": len(items),
                "deduplicated": len(deduped),
                "selected": len(report_items),
                "people_selected": len(people_items),
                "manual_review": len(selected["all_manual"]),
                "insights": len(insights),
            },
            "items": deduped,
            "insights": insights,
            "source_health": source_health,
            "agent_profile": config.agent_profile,
        }

        written_paths: Dict[str, str] = {}
        weekly_path = ""
        dashboard_path = ""
        knowledge_report_path = ""
        feedback_report_path = ""
        draft_paths: List[str] = []
        weekly_should_run = bool(options.weekly or (settings.get("generate_weekly_report", True) and is_weekend(date_text)))
        draft_mode = _resolve_draft_write_mode(settings, options)
        write_drafts = draft_mode == "auto"

        if dry_run:
            log("dry-run: 不写入 Obsidian 文件。", options.verbose)
        else:
            paths = write_daily_outputs(date_text, daily_markdown, people_markdown, raw_payload, self.root)
            written_paths = {key: str(path) for key, path in paths.items()}
            if settings.get("generate_knowledge_report", True):
                knowledge_report_path = str(write_knowledge_report(date_text, insights, self.root))
            if settings.get("enable_feedback_tracking", True):
                feedback_report_path = str(
                    write_feedback_report(date_text, insights, self.root, int(settings.get("feedback_report_limit", 10)))
                )
            if write_drafts:
                draft_paths = [str(path) for path in write_draft_notes(date_text, insights, self.root)]
            if enable_memory:
                memory = update_memory_from_run(memory, date_text, report_items, insights)
                save_memory(memory, self.root)
            if weekly_should_run:
                recent = read_recent_daily_reports(date_text, days=7, root=self.root)
                weekly_markdown = generate_weekly_report(date_text, recent)
                weekly_path = str(write_weekly_output(date_text, weekly_markdown, self.root))
            if options.update_dashboard or settings.get("update_dashboard", True):
                updated = update_home_dashboard(date_text, self.root)
                dashboard_path = str(updated) if updated else ""

        notification_result = notify(settings, {"date": date_text, "paths": written_paths}) if not dry_run else {"sent": False, "reason": "dry-run"}
        run_report = {
            "date": date_text,
            "dry_run": dry_run,
            "use_llm": use_llm,
            "allow_network": allow_network,
            "counts": raw_payload["counts"],
            "paths": written_paths,
            "weekly_path": weekly_path,
            "dashboard_path": dashboard_path,
            "knowledge_report_path": knowledge_report_path,
            "feedback_report_path": feedback_report_path,
            "draft_paths": draft_paths,
            "draft_write_mode": draft_mode,
            "draft_confirmation_required": draft_mode == "ask" and bool(insights),
            "notification": notification_result,
            "weekly_should_run": weekly_should_run,
            "week": week_string(date_text),
        }

        self._record_state(run_report, settings, insights, source_health, dry_run)
        if options.emit_report:
            print(json.dumps(run_report, ensure_ascii=False, indent=2))
        return run_report

    def _record_state(
        self,
        report: Dict[str, Any],
        settings: Dict[str, Any],
        insights: List[Dict[str, Any]],
        source_health: List[Dict[str, Any]],
        dry_run: bool,
    ) -> None:
        try:
            GoldfishState(self.root).record_run(report, settings, insights, source_health)
        except Exception as exc:
            if not dry_run:
                log(f"状态库写入失败：{exc}", True)


def _resolve_draft_write_mode(settings: Dict[str, Any], options: RunOptions) -> str:
    if options.write_drafts:
        return "auto"
    mode = str(options.draft_write_mode or settings.get("draft_write_mode") or "").lower().strip()
    if not mode:
        mode = "auto" if settings.get("auto_create_knowledge_drafts", False) else "suggest"
    if mode not in {"off", "suggest", "ask", "auto"}:
        return "suggest"
    return mode


def _dedupe_selected(groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    seen = set()
    selected: List[Dict[str, Any]] = []
    for group in groups:
        for item in group:
            key = (item.get("url", ""), item.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)
    return selected


def _top(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("score", 0), reverse=True)[: max(limit, 0)]


def _select_report_items(
    items: List[Dict[str, Any]],
    daily_limit: int,
    people_limit: int,
    paper_limit: int,
    github_limit: int,
    product_limit: int,
) -> Dict[str, List[Dict[str, Any]]]:
    people = [item for item in items if item.get("content_type") == "people" or item.get("category") == "people"]
    papers = [item for item in items if item.get("content_type") == "paper" or item.get("category") == "research"]
    open_source = [item for item in items if item.get("content_type") == "open_source" or item.get("category") == "open_source"]
    products = [item for item in items if item.get("content_type") == "product" or item.get("category") == "product"]
    other = [
        item
        for item in items
        if item not in people and item not in papers and item not in open_source and item not in products
    ]
    manual = [item for item in items if item.get("needs_manual_review")]
    selected_people = _top(people, people_limit)
    selected_papers = _top(papers, paper_limit)
    selected_open_source = _top(open_source, github_limit)
    selected_products = _top(products, product_limit)
    selected_other = _top(other, daily_limit)
    selected = _dedupe_selected([selected_other, selected_people, selected_papers, selected_open_source, selected_products, manual[:20]])
    return {"items": selected, "people": selected_people, "all_manual": manual}
