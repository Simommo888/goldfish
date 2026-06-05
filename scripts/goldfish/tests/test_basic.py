import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parents[1]
ROOT = AGENT_DIR.parents[1]
sys.path.insert(0, str(AGENT_DIR))

from modules.classifier import classify_item
from modules.agent_memory import forget_memory, load_memory, memory_context, remember_memory, review_memory
from modules.agent_loop import make_plan, run_agent_loop
from modules.command_router import CommandRouter
from modules.conversation_agent import ChatSession
from modules.config_loader import load_config
from modules.external_cli import list_external_tools, run_external_tool
from modules.feishu_qr_setup import build_pairing_urls, is_valid_feishu_app_credentials, is_valid_feishu_webhook, render_terminal_qr
from modules.insight_extractor import extract_insights
from modules.intent_router import route_intent
from modules.model_setup import configure_environment, find_profile, redact_secret_text
from modules.notifier import feishu_status, send_feishu_test
from modules.providers.registry import resolve_llm_connection
from modules.rag_client import RagConfig, rag_query, rag_search, rag_status
from modules.report_generator import generate_daily_report
from modules.response_formatter import format_tool_response, infer_response_kind, render_markdown, response_system_prompt
from modules.search_engine import search_goldfish
from modules.scorer import score_item
from modules.setup_agent import SetupSession, configure_search_environment, find_search_provider
from modules.skill_router import select_skills
from modules.skill_loader import list_skills, load_skill
from modules.source_health import build_source_health_records
from modules.state_store import GoldfishState
from modules.token_meter import context_energy_bar, estimate_tokens
import modules.tool_registry as tool_registry_module
from modules.tool_planner import plan_tool, validate_tool_plan
from modules.web_researcher import generate_research_markdown, rule_based_synthesis
from modules.web_researcher import _gdelt_results_from_payload, _hackernews_results_from_payload, _jina_results_from_text, _search_provider_order, _tavily_results_from_payload


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class TestDailyAiNewsAgentBasic(unittest.TestCase):
    def test_config_files_can_load(self):
        config = load_config(AGENT_DIR / "config")
        self.assertIn("official", config.sources)
        self.assertIn("high_priority_keywords", config.keywords)
        self.assertTrue(config.people.get("people"))
        self.assertIn("mission", config.agent_profile)

    def test_json_files_are_valid(self):
        for path in (AGENT_DIR / "config").glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_response_formats_are_loaded_and_render_markdown(self):
        config = load_config(AGENT_DIR / "config")
        self.assertIn("research", config.response_formats.get("templates", {}))
        self.assertEqual(infer_response_kind("research MCP monetization opportunity"), "business_idea")
        prompt = response_system_prompt("research", "Simplified Chinese")
        self.assertIn("goldfish", prompt)
        self.assertIn("关键依据", prompt)
        rendered = render_markdown(
            "default",
            {
                "direct_answer": "可以这样做。",
                "context": ["先固定模板。"],
                "judgment": "格式应由程序约束。",
                "next_actions": ["接入聊天链路。"],
            },
        )
        self.assertIn("goldfish", rendered)
        self.assertIn("▌ 结论", rendered)
        self.assertIn("▌ 下一步", rendered)

    def test_token_meter_context_energy_bar(self):
        self.assertIn("100%", context_energy_bar(100, 100))
        self.assertIn("  0%", context_energy_bar(0, 100))
        self.assertGreater(estimate_tokens("goldfish ??"), 0)

    def test_scorer_scores_example(self):
        config = load_config(AGENT_DIR / "config")
        item = {
            "title": "New AI coding agent with MCP and RAG support",
            "summary": "A developer tools product launch for knowledge base workflows.",
            "source_priority": 5,
        }
        scored = score_item(item, config.keywords)
        self.assertGreater(scored["score"], 5)
        self.assertTrue(scored["score_reasons"])

    def test_classifier_classifies_example(self):
        config = load_config(AGENT_DIR / "config")
        item = {"title": "Agent workflow automation with tool use", "summary": ""}
        self.assertEqual(classify_item(item, config.keywords), "agent")

    def test_report_generator_outputs_markdown(self):
        item = {
            "title": "Example AI news",
            "source_name": "Example",
            "category": "agent",
            "url": "https://example.com",
            "published": "2026-05-26",
            "one_sentence_summary": "Example summary.",
            "why_important": "Important.",
            "value_for_me": "Useful.",
            "action": "Read.",
            "suggested_location": "[[Agent-MOC]]",
            "score": 8,
            "score_reasons": ["test"],
        }
        markdown = generate_daily_report("2026-05-26", [item], [])
        self.assertIn("# AI 情报日报 - 2026-05-26", markdown)
        self.assertIn("Example AI news", markdown)

    def test_insight_extractor_outputs_suggestion(self):
        memory = load_memory(ROOT)
        item = {
            "title": "Agent workflow automation product launch",
            "summary": "A new Agent tool for AI application developers.",
            "one_sentence_summary": "A new Agent tool was launched.",
            "why_important": "It may improve AI app development workflows.",
            "value_for_me": "Can become a project idea.",
            "action": "Study the workflow.",
            "category": "agent",
            "source_name": "Example",
            "url": "https://example.com",
            "score": 9,
        }
        insights = extract_insights([item], memory, limit=3, min_score=5)
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]["target_type"], "project_idea")

    def test_provider_registry_resolves_deepseek_default(self):
        connection = resolve_llm_connection(
            {
                "llm_provider": "deepseek",
                "llm_model": "deepseek-v4-pro",
                "llm_base_url": "https://api.deepseek.com",
            }
        )
        self.assertEqual(connection["provider"], "deepseek")
        self.assertEqual(connection["model"], "deepseek-v4-pro")
        self.assertEqual(connection["base_url"], "https://api.deepseek.com")

    def test_provider_registry_prefers_settings_over_stale_model_env(self):
        old_provider = os.environ.get("AI_NEWS_LLM_PROVIDER")
        old_model = os.environ.get("AI_NEWS_LLM_MODEL")
        try:
            os.environ["AI_NEWS_LLM_PROVIDER"] = "openai"
            os.environ["AI_NEWS_LLM_MODEL"] = "stale-model"
            connection = resolve_llm_connection(
                {
                    "llm_provider": "deepseek",
                    "llm_model": "deepseek-v4-pro",
                    "llm_base_url": "https://api.deepseek.com",
                }
            )
            self.assertEqual(connection["provider"], "deepseek")
            self.assertEqual(connection["model"], "deepseek-v4-pro")
        finally:
            _restore_env("AI_NEWS_LLM_PROVIDER", old_provider)
            _restore_env("AI_NEWS_LLM_MODEL", old_model)

    def test_model_setup_helpers_do_not_require_files(self):
        profile = find_profile("deepseek-v4-pro")
        configured = configure_environment(profile, "sk-test-do-not-use-123456", persist_user=False)
        self.assertEqual(configured["provider"], "deepseek")
        self.assertEqual(configured["model"], "deepseek-v4-pro")
        self.assertIn("***REDACTED***", redact_secret_text("api_key=sk-test-do-not-use-123456"))
        self.assertIn("task-20260602-abcdef", redact_secret_text("task-20260602-abcdef"))

    def test_memory_v2_remember_review_and_forget(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remembered = remember_memory(
                "I care about MCP commercial opportunities in goldfish",
                kind="business",
                root=root,
            )
            self.assertEqual(remembered["status"], "ok")
            memory = load_memory(root)
            self.assertEqual(memory["schema_version"], 2)
            self.assertTrue(memory["long_term_facts"])
            context = memory_context(memory)
            self.assertIn("MCP commercial opportunities", context)
            review = review_memory(root)
            self.assertEqual(review["counts"]["long_term_facts"], 1)
            removed = forget_memory("MCP commercial", root=root)
            self.assertGreaterEqual(removed["removed_count"], 1)
            self.assertFalse(load_memory(root)["long_term_facts"])

    def test_command_router_routes_search(self):
        routed = CommandRouter().route('/search MCP --limit 3', {"no_llm": True})
        self.assertEqual(routed.tool_name, "search")
        self.assertIn("MCP", routed.args["query"])
        self.assertEqual(routed.args["limit"], 3)

    def test_command_router_routes_memory_commands(self):
        remember = CommandRouter().route('/remember I prefer Agent commercialization --kind preference', {"no_llm": True})
        self.assertEqual(remember.tool_name, "memory_remember")
        self.assertIn("Agent commercialization", remember.args["text"])
        self.assertEqual(remember.args["kind"], "preference")
        forget = CommandRouter().route('/forget Agent commercialization', {"no_llm": True})
        self.assertEqual(forget.tool_name, "memory_forget")
        self.assertIn("Agent commercialization", forget.args["query"])
        review = CommandRouter().route('/memory review', {"no_llm": True})
        self.assertEqual(review.tool_name, "memory_review")

    def test_command_router_routes_research(self):
        routed = CommandRouter().route('/research MCP servers --limit 3 --no-llm', {"no_llm": True})
        self.assertEqual(routed.tool_name, "web_search")
        self.assertIn("MCP servers", routed.args["query"])
        self.assertEqual(routed.args["limit"], 3)
        self.assertTrue(routed.args["no_llm"])
        self.assertEqual(routed.args["mode"], "research")

    def test_command_router_routes_web_search(self):
        routed = CommandRouter().route('/web MCP servers --limit 3', {"no_llm": True})
        self.assertEqual(routed.tool_name, "web_search")
        self.assertIn("MCP servers", routed.args["query"])
        self.assertEqual(routed.args["limit"], 3)

    def test_command_router_routes_rag_commands(self):
        answer = CommandRouter().route('/rag goldfish project --top-k 3', {"no_llm": True})
        self.assertEqual(answer.tool_name, "rag_query")
        self.assertIn("goldfish", answer.args["question"])
        self.assertEqual(answer.args["top_k"], 3)
        search = CommandRouter().route('/rag-search MCP --top-k 2', {"no_llm": True})
        self.assertEqual(search.tool_name, "rag_search")
        self.assertEqual(search.args["query"], "MCP")
        self.assertEqual(search.args["top_k"], 2)
        status = CommandRouter().route('/rag-status', {"no_llm": True})
        self.assertEqual(status.tool_name, "rag_status")

    def test_command_router_routes_natural_language_to_rag(self):
        routed = CommandRouter().route("please query my knowledge base about goldfish project", {"no_llm": True})
        self.assertEqual(routed.tool_name, "rag_query")
        self.assertIn("goldfish", routed.args["query"])

    def test_command_router_routes_generic_chinese_lookup_to_knowledge_lookup(self):
        routed = CommandRouter().route("\u5e2e\u6211\u67e5\u4e00\u4e0b\u6625\u5929\u76f8\u5173\u5185\u5bb9", {"no_llm": True})
        self.assertEqual(routed.tool_name, "knowledge_lookup")
        self.assertEqual(routed.args["query"], "\u6625\u5929")
        self.assertEqual(routed.args["top_k"], 8)
        self.assertEqual(routed.args["web_limit"], 5)

    def test_command_router_explicit_latest_still_routes_to_web(self):
        routed = CommandRouter().route("\u5e2e\u6211\u67e5\u4e00\u4e0b\u4eca\u5929AI\u65b0\u95fb", {"no_llm": True})
        self.assertEqual(routed.tool_name, "web_search")
        self.assertEqual(routed.args["search_provider"], "news")

    def test_command_router_routes_chinese_today_ai_news_to_web_search(self):
        routed = CommandRouter().route("请告诉我今天发生的AI大事", {"no_llm": True})
        self.assertEqual(routed.tool_name, "web_search")
        self.assertEqual(routed.args["search_provider"], "news")
        self.assertIn("AI大事", routed.args["query"])

    def test_intent_router_uses_config_for_chinese_today_ai_news(self):
        routed = route_intent("请告诉我今天发生的AI大事", {"no_llm": True})
        self.assertIsNotNone(routed)
        self.assertEqual(routed.tool_name, "web_search")
        self.assertEqual(routed.args["search_provider"], "news")

    def test_tool_planner_validates_model_tool_choice(self):
        tools = [
            {"name": "web_search", "description": "Search public web", "mutating": True},
            {"name": "search", "description": "Search local notes", "mutating": False},
        ]
        plan = validate_tool_plan(
            {
                "tool": "web_search",
                "args": {"query": "OpenAI latest news today", "limit": 5, "unsafe": "ignored"},
                "confidence": 0.9,
                "reason": "Needs current public information.",
            },
            "OpenAI latest news today",
            tools,
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool_name, "web_search")
        self.assertEqual(plan.args["search_provider"], "news")
        self.assertNotIn("unsafe", plan.args)
        chinese_plan = validate_tool_plan(
            {"tool": "web_search", "args": {"query": "AI"}, "confidence": 0.9},
            "\u8bf7\u544a\u8bc9\u6211\u4eca\u5929\u53d1\u751f\u7684AI\u5927\u4e8b",
            tools,
        )
        self.assertIsNotNone(chinese_plan)
        self.assertEqual(chinese_plan.args["search_provider"], "news")

    def test_tool_planner_normalizes_generic_lookup_to_knowledge_lookup(self):
        tools = [
            {"name": "web_search", "description": "Search public web", "mutating": True},
            {"name": "knowledge_lookup", "description": "Search RAG first then web", "mutating": False},
        ]
        plan = validate_tool_plan(
            {"tool": "web_search", "args": {"query": "\u6625\u5929"}, "confidence": 0.9},
            "\u5e2e\u6211\u67e5\u4e00\u4e0b\u6625\u5929\u76f8\u5173\u5185\u5bb9",
            tools,
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool_name, "knowledge_lookup")
        self.assertEqual(plan.args["query"], "\u6625\u5929")
        self.assertEqual(plan.args["top_k"], 8)
        self.assertEqual(plan.args["web_limit"], 5)

    def test_tool_planner_uses_provider_and_low_confidence_fallback(self):
        class FakeProvider:
            def generate_json(self, messages, temperature=0.2):
                return {
                    "tool": "search",
                    "args": {"query": "MCP"},
                    "confidence": 0.8,
                    "reason": "Local lookup requested.",
                }

        tools = [{"name": "search", "description": "Search local notes", "mutating": False}]
        plan = plan_tool("search previous MCP notes", tools, provider=FakeProvider())
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool_name, "search")
        low = validate_tool_plan({"tool": "search", "args": {"query": "MCP"}, "confidence": 0.1}, "MCP", tools)
        self.assertIsNone(low)

    def test_tool_planner_validates_rag_tool_choice(self):
        tools = [
            {"name": "rag_query", "description": "Ask local RAG", "mutating": False},
            {"name": "rag_status", "description": "Check RAG", "mutating": False},
        ]
        plan = validate_tool_plan(
            {"tool": "rag_query", "args": {"question": "goldfish project", "top_k": 3, "api_key": "nope"}, "confidence": 0.9},
            "query my knowledge base about goldfish project",
            tools,
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool_name, "rag_query")
        self.assertEqual(plan.args["top_k"], 3)
        self.assertNotIn("api_key", plan.args)
        status = validate_tool_plan({"tool": "rag_status", "args": {"query": "ignored"}, "confidence": 0.9}, "rag status", tools)
        self.assertIsNotNone(status)
        self.assertEqual(status.args, {})

    def test_command_router_routes_agent(self):
        routed = CommandRouter().route('/agent research MCP business opportunities --max-steps 3 --no-llm', {"no_llm": True})
        self.assertEqual(routed.tool_name, "agent")
        self.assertIn("MCP business opportunities", routed.args["goal"])
        self.assertEqual(routed.args["max_steps"], 3)
        self.assertTrue(routed.args["no_llm"])

    def test_external_cli_lists_and_dry_runs(self):
        tools = list_external_tools()
        names = {tool["name"] for tool in tools}
        self.assertIn("rg_search", names)
        result = run_external_tool("rg_search", {"query": "goldfish", "path": "scripts/goldfish"}, dry_run=True)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["dry_run"])

    def test_command_router_routes_external_exec(self):
        routed = CommandRouter().route('/exec rg_search query=MCP path=scripts/goldfish', {"no_llm": True})
        self.assertEqual(routed.tool_name, "external_cli")
        self.assertEqual(routed.args["name"], "rg_search")
        self.assertEqual(routed.args["args"]["query"], "MCP")

    def test_agent_loop_plans_research_goal(self):
        plan = make_plan("research MCP server commercial opportunities", max_steps=3, no_save=True)
        self.assertEqual(plan[0].tool, "web_search")
        self.assertEqual(plan[0].status, "search")
        self.assertEqual(plan[0].args["mode"], "research")
        self.assertTrue(plan[0].args["no_save"])

    def test_agent_loop_plans_rag_goal(self):
        plan = make_plan("query my knowledge base about goldfish project", max_steps=3, no_save=True)
        self.assertIn("rag_query", [step.tool for step in plan])

    def test_agent_loop_plans_generic_lookup_as_knowledge_lookup(self):
        plan = make_plan("\u5e2e\u6211\u67e5\u4e00\u4e0b\u6625\u5929\u76f8\u5173\u5185\u5bb9", max_steps=3, no_save=True)
        tools = [step.tool for step in plan]
        self.assertIn("knowledge_lookup", tools)
        self.assertNotIn("web_search", tools)
        lookup_step = next(step for step in plan if step.tool == "knowledge_lookup")
        self.assertEqual(lookup_step.args["query"], "\u6625\u5929")

    def test_agent_loop_runs_with_fake_registry_and_workspace(self):
        class FakeRegistry:
            def __init__(self):
                self.calls = []

            def execute(self, name, args=None):
                self.calls.append((name, args or {}))
                if name == "web_search":
                    return {
                        "status": "ok",
                        "mode": "research",
                        "research": {
                            "query": (args or {}).get("query", ""),
                            "results_count": 1,
                            "pages_count": 0,
                            "report_path": "",
                        },
                    }
                if name == "skills":
                    return {"status": "ok", "skill": {"name": (args or {}).get("name", "")}}
                if name == "memory_show":
                    return {"status": "ok", "memory": {}}
                return {"status": "ok"}

        result = run_agent_loop(
            "research MCP commercial opportunities",
            registry=FakeRegistry(),
            max_steps=2,
            no_llm=True,
            no_save=True,
            root=ROOT,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["execution"]["mode"], "plan_execute")
        self.assertTrue(Path(result["task_path"]).exists())
        self.assertTrue((Path(result["task_path"]) / "goal.md").exists())
        self.assertTrue((Path(result["task_path"]) / "observations.json").exists())
        self.assertTrue((Path(result["task_path"]) / "execution_state.json").exists())
        self.assertTrue((Path(result["task_path"]) / "plan_revisions.jsonl").exists())
        self.assertTrue((Path(result["task_path"]) / "skills.md").exists())
        self.assertTrue((Path(result["task_path"]) / "selected_skills.json").exists())
        self.assertEqual(result["observations"][0]["tool"], "skills")
        self.assertEqual(result["observations"][1]["tool"], "web_search")
        self.assertTrue(result["selected_skills"])

    def test_agent_loop_revises_plan_after_research_failure(self):
        class FakeRegistry:
            def execute(self, name, args=None):
                if name == "skills":
                    return {"status": "ok", "skill": {"name": (args or {}).get("name", "")}}
                if name == "web_search":
                    return {"status": "error", "error": "network unavailable"}
                if name == "search":
                    return {"status": "ok", "query": (args or {}).get("query", ""), "results": []}
                if name == "memory_show":
                    return {"status": "ok", "memory": {}}
                return {"status": "ok"}

        result = run_agent_loop(
            "web MCP server commercial opportunities",
            registry=FakeRegistry(),
            max_steps=4,
            no_llm=True,
            no_save=True,
            root=ROOT,
        )
        self.assertGreaterEqual(result["execution"]["plan_revisions"], 2)
        self.assertEqual(result["observations"][0]["tool"], "skills")
        self.assertEqual(result["observations"][1]["tool"], "web_search")
        self.assertEqual(result["observations"][2]["tool"], "search")
        self.assertIn("web_search_failed_add_local_search", result["plan_revisions"][1]["reason"])

    def test_agent_loop_records_step_timeout(self):
        class SlowRegistry:
            def execute(self, name, args=None):
                time.sleep(0.2)
                return {"status": "ok"}

        with tempfile.TemporaryDirectory() as temp:
            result = run_agent_loop(
                "show tools",
                registry=SlowRegistry(),
                max_steps=1,
                no_llm=True,
                no_save=True,
                root=Path(temp),
                step_timeout=0.05,
                task_timeout=2,
            )
        self.assertEqual(result["observations"][0]["failure_type"], "timeout")
        self.assertTrue(result["observations"][0]["timed_out"])
        self.assertEqual(result["failure_summary"]["timeouts"], 1)
        self.assertIn("failure_policy", result["execution"])

    def test_agent_loop_stops_after_consecutive_failures(self):
        class FailingRegistry:
            def execute(self, name, args=None):
                return {"status": "error", "error": f"{name} failed"}

        with tempfile.TemporaryDirectory() as temp:
            result = run_agent_loop(
                "show tools",
                registry=FailingRegistry(),
                max_steps=3,
                no_llm=True,
                no_save=True,
                root=Path(temp),
                max_consecutive_failures=1,
            )
        self.assertEqual(result["execution"]["stop_reason"], "max_consecutive_failures_reached")
        self.assertEqual(result["failure_summary"]["consecutive_failures"], 1)

    def test_rag_client_shapes_with_fake_transport(self):
        config = RagConfig(
            enabled=True,
            base_url="http://127.0.0.1:8020",
            health_endpoint="/api/health",
            stats_endpoint="/api/rag/stats",
            ask_endpoint="/api/rag/ask",
            search_endpoint="/api/rag/search",
            retrieval_mode="hybrid",
            top_k=8,
            use_llm=False,
            timeout_seconds=5,
            config_path=AGENT_DIR / "config" / "rag.json",
        )

        def fake_transport(method, url, payload, timeout):
            if url.endswith("/api/health"):
                return {"status": "ok", "service": "RAG Knowledge Base"}
            if url.endswith("/api/rag/stats"):
                return {"documents": 2, "chunks": 3, "embeddings": 3, "kb_root": "D:/My-Knowledge-Base"}
            if url.endswith("/api/rag/ask"):
                self.assertEqual(payload["question"], "goldfish project")
                return {
                    "question": payload["question"],
                    "answer": "goldfish is an intelligence and knowledge deposition agent.",
                    "sources": [{"title": "Goldfish", "file_path": "README.md", "content": "Agent", "score": 1.0}],
                    "llm_used": False,
                    "model": "",
                    "warnings": [],
                }
            if url.endswith("/api/rag/search"):
                self.assertEqual(payload["query"], "MCP")
                return [{"title": "MCP", "file_path": "note.md", "content": "MCP note", "score": 0.8}]
            raise AssertionError(url)

        status = rag_status(transport=fake_transport, config=config)
        self.assertEqual(status["status"], "ok")
        answer = rag_query("goldfish project", top_k=3, transport=fake_transport, config=config)
        self.assertEqual(answer["status"], "ok")
        self.assertEqual(answer["sources"][0]["file_path"], "README.md")
        search = rag_search("MCP", transport=fake_transport, config=config)
        self.assertEqual(search["status"], "ok")
        self.assertEqual(search["results"][0]["title"], "MCP")
        self.assertEqual(search["result_count"], 1)

    def test_rag_client_basic_error_handling(self):
        disabled = RagConfig(
            enabled=False,
            base_url="http://127.0.0.1:8020",
            health_endpoint="/api/health",
            stats_endpoint="/api/rag/stats",
            ask_endpoint="/api/rag/ask",
            search_endpoint="/api/rag/search",
            retrieval_mode="hybrid",
            top_k=8,
            use_llm=False,
            timeout_seconds=5,
            config_path=AGENT_DIR / "config" / "rag.json",
        )
        enabled = RagConfig(
            enabled=True,
            base_url="http://127.0.0.1:8020",
            health_endpoint="/api/health",
            stats_endpoint="/api/rag/stats",
            ask_endpoint="/api/rag/ask",
            search_endpoint="/api/rag/search",
            retrieval_mode="hybrid",
            top_k=8,
            use_llm=False,
            timeout_seconds=5,
            config_path=AGENT_DIR / "config" / "rag.json",
        )

        empty_query = rag_query("", config=enabled)
        self.assertEqual(empty_query["status"], "error")
        self.assertEqual(empty_query["error_type"], "empty_query")
        missing_kb = rag_search("MCP", config=disabled)
        self.assertEqual(missing_kb["status"], "error")
        self.assertEqual(missing_kb["error_type"], "rag_disabled")

        def timeout_transport(method, url, payload, timeout):
            raise TimeoutError("timed out")

        timeout_result = rag_search("MCP", transport=timeout_transport, config=enabled)
        self.assertEqual(timeout_result["status"], "error")
        self.assertEqual(timeout_result["error_type"], "timeout")
        self.assertEqual(timeout_result["result_count"], 0)

        def failing_transport(method, url, payload, timeout):
            raise RuntimeError("retrieval backend failed")

        failure = rag_query("goldfish project", transport=failing_transport, config=enabled)
        self.assertEqual(failure["status"], "error")
        self.assertEqual(failure["error_type"], "retrieval_failed")
        self.assertEqual(failure["source_count"], 0)

    def test_knowledge_lookup_runs_rag_then_web_and_formats_two_blocks(self):
        old_rag_search = tool_registry_module.rag_search
        old_search_public_web = tool_registry_module.search_public_web

        def fake_rag_search(query, top_k=None, retrieval_mode=None, category="all"):
            return {
                "status": "ok",
                "query": query,
                "result_count": 1,
                "results": [
                    {
                        "title": "Spring note",
                        "file_path": "notes/spring.md",
                        "heading": "Season",
                        "score": 0.91,
                        "content": "A local knowledge-base chunk about spring.",
                    }
                ],
            }

        def fake_web_search(query, limit=5, timeout=12, provider=None, timespan=None):
            return [
                {
                    "title": "Spring public source",
                    "url": "https://example.com/spring",
                    "snippet": "A public web result about spring.",
                    "source": "Fake Search",
                    "provider_order": ["fake"],
                }
            ]

        try:
            tool_registry_module.rag_search = fake_rag_search
            tool_registry_module.search_public_web = fake_web_search
            result = tool_registry_module._tool_knowledge_lookup({"query": "spring", "top_k": 2, "web_limit": 2})
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["strategy"], ["rag_search", "web_search"])
            self.assertTrue(result["safety"]["rag_first"])
            self.assertTrue(result["safety"]["separate_blocks"])
            self.assertFalse(result["safety"]["merged_claims"])
            self.assertEqual(result["rag"]["result_count"], 1)
            self.assertEqual(result["web"]["count"], 1)
            rendered = format_tool_response("knowledge_lookup", result, "Knowledge lookup:")
            self.assertIn("RAG 查询结果", rendered)
            self.assertIn("联网查询结果", rendered)
            self.assertIn("一致性约束", rendered)
        finally:
            tool_registry_module.rag_search = old_rag_search
            tool_registry_module.search_public_web = old_search_public_web

    def test_agent_loop_can_call_rag_and_record_timeout(self):
        class SlowRagRegistry:
            def __init__(self):
                self.tools = {
                    "skills": type("Spec", (), {"timeout_seconds": 1})(),
                    "rag_query": type("Spec", (), {"timeout_seconds": 1})(),
                    "memory_show": type("Spec", (), {"timeout_seconds": 1})(),
                }

            def execute(self, name, args=None):
                if name == "skills":
                    return {"status": "ok", "skill": {"name": (args or {}).get("name", "")}}
                if name == "rag_query":
                    time.sleep(0.2)
                    return {"status": "ok", "sources": []}
                if name == "memory_show":
                    return {"status": "ok", "memory": {}}
                return {"status": "ok"}

        with tempfile.TemporaryDirectory() as temp:
            result = run_agent_loop(
                "query my knowledge base about goldfish project",
                registry=SlowRagRegistry(),
                max_steps=3,
                no_llm=True,
                no_save=True,
                root=Path(temp),
                step_timeout=0.05,
                task_timeout=2,
            )
        rag_observations = [obs for obs in result["observations"] if obs.get("tool") == "rag_query"]
        self.assertTrue(rag_observations)
        self.assertEqual(rag_observations[0]["failure_type"], "timeout")
        self.assertTrue(rag_observations[0]["timed_out"])

    def test_skill_router_selects_business_and_draft_skills(self):
        business = select_skills("帮我从 MCP 新闻里提炼 3 个商业想法和 MVP")
        self.assertIn("business-idea", {skill["name"] for skill in business})
        draft = select_skills("把这个内容沉淀成永久笔记和 Prompt 草稿")
        names = {skill["name"] for skill in draft}
        self.assertIn("draft-writing", names)
        self.assertIn("knowledge-routing", names)

    def test_command_router_routes_skill_like_natural_language_to_agent(self):
        routed = CommandRouter().route("帮我把这条新闻沉淀成永久笔记和商业想法", {"no_llm": True})
        self.assertEqual(routed.tool_name, "agent")
        self.assertIn("永久笔记", routed.args["goal"])

    def test_skills_can_load(self):
        skills = list_skills()
        names = {skill["name"] for skill in skills}
        self.assertIn("business-idea", names)
        self.assertIn("internet-search", names)
        self.assertIn("tavily-search", names)
        self.assertIn("jina-search", names)
        business = load_skill("business-idea")
        self.assertIn("Target user", business["content"])

    def test_search_provider_order_uses_env_and_fallback(self):
        old_tavily = os.environ.get("TAVILY_API_KEY")
        old_jina = os.environ.get("JINA_API_KEY")
        old_provider = os.environ.get("GOLDFISH_SEARCH_PROVIDER")
        old_ignore = os.environ.get("GOLDFISH_IGNORE_USER_ENV")
        try:
            os.environ["GOLDFISH_IGNORE_USER_ENV"] = "1"
            os.environ.pop("TAVILY_API_KEY", None)
            os.environ.pop("JINA_API_KEY", None)
            os.environ.pop("GOLDFISH_SEARCH_PROVIDER", None)
            self.assertEqual(_search_provider_order(), ["duckduckgo"])
            os.environ["JINA_API_KEY"] = "test-key"
            self.assertEqual(_search_provider_order()[0], "jina")
            os.environ["TAVILY_API_KEY"] = "test-key"
            self.assertEqual(_search_provider_order()[0], "tavily")
            self.assertEqual(_search_provider_order("jina")[0], "jina")
            self.assertEqual(_search_provider_order("news")[-3:], ["hackernews", "gdelt", "duckduckgo"])
            self.assertEqual(_search_provider_order("duckduckgo"), ["duckduckgo"])
        finally:
            _restore_env("TAVILY_API_KEY", old_tavily)
            _restore_env("JINA_API_KEY", old_jina)
            _restore_env("GOLDFISH_SEARCH_PROVIDER", old_provider)
            _restore_env("GOLDFISH_IGNORE_USER_ENV", old_ignore)

    def test_tavily_and_jina_search_payload_parsers(self):
        tavily = _tavily_results_from_payload(
            {
                "results": [
                    {
                        "title": "Example Tavily",
                        "url": "https://example.com/tavily",
                        "content": "Tavily snippet",
                    }
                ]
            }
        )
        jina = _jina_results_from_text(
            "Title: Example Jina\n"
            "URL Source: https://example.com/jina\n"
            "Description: Jina snippet\n"
        )
        self.assertEqual(tavily[0]["source"], "Tavily Search")
        self.assertEqual(tavily[0]["url"], "https://example.com/tavily")
        self.assertEqual(jina[0]["source"], "Jina Search")
        self.assertEqual(jina[0]["url"], "https://example.com/jina")

    def test_no_key_realtime_search_payload_parsers(self):
        hn = _hackernews_results_from_payload(
            {
                "hits": [
                    {
                        "title": "OpenAI realtime story",
                        "url": "https://example.com/hn",
                        "created_at": "2026-06-01T10:00:00Z",
                        "points": 3,
                        "num_comments": 2,
                    }
                ]
            }
        )
        gdelt = _gdelt_results_from_payload(
            {
                "articles": [
                    {
                        "title": "OpenAI latest article",
                        "url": "https://example.com/gdelt",
                        "domain": "example.com",
                        "seendate": "20260601T100000Z",
                    }
                ]
            }
        )
        self.assertEqual(hn[0]["source"], "Hacker News Algolia")
        self.assertEqual(hn[0]["url"], "https://example.com/hn")
        self.assertEqual(gdelt[0]["source"], "GDELT DOC API")
        self.assertEqual(gdelt[0]["published"], "20260601T100000Z")

    def test_source_health_records(self):
        sources = [{"name": "Example", "enabled": True}]
        items = [
            {
                "source_name": "Example",
                "title": "MCP agent launch",
                "score": 8,
                "needs_manual_review": False,
            }
        ]
        records = build_source_health_records(sources, items)
        self.assertEqual(records[0]["status"], "success")
        self.assertGreater(records[0]["quality_score"], 0)

    def test_command_router_routes_dry_run(self):
        routed = CommandRouter().route("dry-run", {"no_llm": True})
        self.assertEqual(routed.tool_name, "dry_run")
        self.assertTrue(routed.args["no_llm"])

    def test_dry_run_command(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "goldfish.py"),
            "--dry-run",
            "--no-llm",
            "--verbose",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"dry_run": true', result.stdout)
        self.assertIn('"insights"', result.stdout)

    def test_cli_config_check(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "config",
            "check",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("goldfish", result.stdout)

    def test_cli_dry_run(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "dry-run",
            "--no-llm",
            "--verbose",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"dry_run": true', result.stdout)

    def test_cli_chat_once(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "chat",
            "--no-llm",
            "--once",
            "/config",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("sources_categories", result.stdout)

    def test_chat_model_points_to_setup(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "chat",
            "--no-llm",
            "--once",
            "/model",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("goldfish setup", result.stdout)

    def test_chat_model_list_works(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "chat",
            "--no-llm",
            "--once",
            "/model list",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("DeepSeek", result.stdout)

    def test_setup_language_list_works(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "setup",
            "--once",
            "/language list",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Available output languages", result.stdout)

    def test_setup_search_list_works(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "setup",
            "--once",
            "/search list",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Tavily Search API", result.stdout)
        self.assertIn("Jina Search", result.stdout)
        self.assertIn("DuckDuckGo", result.stdout)

    def test_setup_feishu_status_works(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "setup",
            "--once",
            "/feishu status",
        ]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(command, cwd=str(ROOT), env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("当前飞书通知配置", result.stdout)

    def test_setup_search_noninteractive_does_not_prompt_for_key(self):
        old_tavily = os.environ.get("TAVILY_API_KEY")
        old_ignore = os.environ.get("GOLDFISH_IGNORE_USER_ENV")
        try:
            os.environ["GOLDFISH_IGNORE_USER_ENV"] = "1"
            os.environ.pop("TAVILY_API_KEY", None)
            answer = SetupSession(interactive=False).handle("/search tavily")
            self.assertIn("requires `TAVILY_API_KEY`", answer)
            self.assertIn("goldfish setup", answer)
        finally:
            _restore_env("TAVILY_API_KEY", old_tavily)
            _restore_env("GOLDFISH_IGNORE_USER_ENV", old_ignore)

    def test_feishu_status_and_test_payload(self):
        old_url = os.environ.get("FEISHU_WEBHOOK_URL")
        old_secret = os.environ.get("FEISHU_WEBHOOK_SECRET")
        old_app_id = os.environ.get("FEISHU_APP_ID")
        old_app_secret = os.environ.get("FEISHU_APP_SECRET")
        old_ignore = os.environ.get("GOLDFISH_IGNORE_USER_ENV")
        captured = {}

        def fake_transport(url, payload, timeout):
            captured["url"] = url
            captured["payload"] = payload
            captured["timeout"] = timeout
            return {"code": 0, "msg": "success"}

        try:
            os.environ["GOLDFISH_IGNORE_USER_ENV"] = "1"
            os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/open-apis/bot/v2/hook/test"
            os.environ["FEISHU_WEBHOOK_SECRET"] = "test-secret"
            os.environ["FEISHU_APP_ID"] = "cli_test_app_id"
            os.environ["FEISHU_APP_SECRET"] = "test-app-secret"
            status = feishu_status({"enable_notifications": True, "notification_channels": ["feishu"], "enable_feishu_app_integration": True})
            self.assertTrue(status["has_app_id"])
            self.assertTrue(status["has_app_secret"])
            self.assertTrue(status["app_integration_enabled"])
            self.assertTrue(status["has_webhook_url"])
            self.assertTrue(status["has_signing_secret"])
            result = send_feishu_test({"feishu_message_type": "post", "feishu_timeout_seconds": 3}, transport=fake_transport)
            self.assertTrue(result["sent"])
            self.assertEqual(captured["timeout"], 3)
            self.assertEqual(captured["payload"]["msg_type"], "post")
            self.assertIn("timestamp", captured["payload"])
            self.assertIn("sign", captured["payload"])
        finally:
            _restore_env("FEISHU_WEBHOOK_URL", old_url)
            _restore_env("FEISHU_WEBHOOK_SECRET", old_secret)
            _restore_env("FEISHU_APP_ID", old_app_id)
            _restore_env("FEISHU_APP_SECRET", old_app_secret)
            _restore_env("GOLDFISH_IGNORE_USER_ENV", old_ignore)

    def test_feishu_qr_helpers_validate_safe_webhooks(self):
        self.assertTrue(is_valid_feishu_app_credentials("cli_aaab080165f8dcff", "bBMAFXY0hEQ5ioPFWkg1gdAHuCfFZxPC"))
        self.assertFalse(is_valid_feishu_app_credentials("app_aaab080165f8dcff", "bBMAFXY0hEQ5ioPFWkg1gdAHuCfFZxPC"))
        self.assertFalse(is_valid_feishu_app_credentials("cli_aaab080165f8dcff", "short"))
        self.assertTrue(is_valid_feishu_webhook("https://open.feishu.cn/open-apis/bot/v2/hook/test"))
        self.assertTrue(is_valid_feishu_webhook("https://open.larksuite.com/open-apis/bot/v2/hook/test"))
        self.assertFalse(is_valid_feishu_webhook("http://open.feishu.cn/open-apis/bot/v2/hook/test"))
        self.assertFalse(is_valid_feishu_webhook("https://example.com/open-apis/bot/v2/hook/test"))
        urls = build_pairing_urls(host="192.168.1.2", port=8765, token="abc")
        self.assertEqual(urls.public_url, "http://192.168.1.2:8765/feishu/setup?token=abc")
        self.assertEqual(urls.local_url, "http://127.0.0.1:8765/feishu/setup?token=abc")
        qr = render_terminal_qr(urls.public_url)
        self.assertIsInstance(qr, str)

    def test_cli_notify_qr_help_is_registered(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "notify",
            "qr",
            "--help",
        ]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(command, cwd=str(ROOT), env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("二维码配置飞书应用 App ID 和 App Secret", result.stdout)

    def test_search_provider_setup_helper_for_duckduckgo(self):
        profile = find_search_provider("duckduckgo")
        self.assertIsNotNone(profile)
        configured = configure_search_environment(profile, persist_user=False)
        self.assertEqual(configured["provider"], "duckduckgo")
        self.assertFalse(configured["api_key_saved"])

    def test_setup_model_list(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "setup",
            "--once",
            "/model list",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("DeepSeek", result.stdout)

    def test_cli_chat_starts_legacy_chat(self):
        command = [sys.executable, str(AGENT_DIR / "cli.py"), "chat"]
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            input="exit\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("goldfish", result.stdout)
        self.assertNotIn("small agent, sharp memory", result.stdout)
        self.assertIn("v0.1.0", result.stdout)
        self.assertIn("session closed", result.stdout)

    def test_interactive_chat_prints_thinking_state(self):
        session = ChatSession(use_llm=False, interactive=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            answer = session.respond("/tools")
        text = output.getvalue()
        self.assertIn("goldfish > analyzing query...", text)
        self.assertIn("goldfish > reading tools...", text)
        self.assertIn("goldfish > answer ready.", text)
        self.assertIn("tools", answer)

    def test_cli_tools_and_history(self):
        tools_command = [sys.executable, str(AGENT_DIR / "cli.py"), "tools"]
        tools = subprocess.run(tools_command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(tools.returncode, 0, msg=tools.stdout + tools.stderr)
        self.assertIn("run_daily", tools.stdout)

        history_command = [sys.executable, str(AGENT_DIR / "cli.py"), "history", "--limit", "3"]
        history = subprocess.run(history_command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(history.returncode, 0, msg=history.stdout + history.stderr)
        self.assertIn("state_db", history.stdout)

    def test_cli_search_and_skills(self):
        search_command = [sys.executable, str(AGENT_DIR / "cli.py"), "search", "MCP", "--limit", "3"]
        search = subprocess.run(search_command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(search.returncode, 0, msg=search.stdout + search.stderr)
        self.assertIn('"query": "MCP"', search.stdout)

        skills_command = [sys.executable, str(AGENT_DIR / "cli.py"), "skills"]
        skills = subprocess.run(skills_command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(skills.returncode, 0, msg=skills.stdout + skills.stderr)
        self.assertIn("business-idea", skills.stdout)

        source_command = [sys.executable, str(AGENT_DIR / "cli.py"), "sources", "health", "--limit", "3"]
        source_health = subprocess.run(source_command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(source_health.returncode, 0, msg=source_health.stdout + source_health.stderr)
        self.assertIn("source_health", source_health.stdout)

    def test_cli_agent_command_runs_without_llm(self):
        command = [
            sys.executable,
            str(AGENT_DIR / "cli.py"),
            "agent",
            "show tools",
            "--no-llm",
            "--max-steps",
            "1",
            "--no-save",
            "--step-timeout",
            "5",
            "--task-timeout",
            "30",
            "--max-failures",
            "2",
            "--max-consecutive-failures",
            "1",
        ]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Agent loop completed:", result.stdout)
        self.assertIn("goldfish · plan_execute", result.stdout)
        self.assertIn("task_id", result.stdout)

    def test_search_engine_returns_shape(self):
        result = search_goldfish("MCP", limit=3, root=ROOT)
        self.assertIn("query", result)
        self.assertIn("results", result)

    def test_web_research_markdown_shape(self):
        results = [{"title": "Example", "url": "https://example.com", "snippet": "Snippet"}]
        pages = [{**results[0], "content": "Content about MCP.", "fetch_status": "success", "error": ""}]
        synthesis = rule_based_synthesis("MCP", results, pages)
        markdown = generate_research_markdown("MCP", results, pages, synthesis)
        self.assertIn("# Web Research - MCP", markdown)
        self.assertIn("https://example.com", markdown)

    def test_state_store_initializes(self):
        state = GoldfishState(ROOT)
        self.assertTrue(state.path.exists())


if __name__ == "__main__":
    unittest.main()
