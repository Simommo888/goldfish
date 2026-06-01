import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parents[1]
ROOT = AGENT_DIR.parents[1]
sys.path.insert(0, str(AGENT_DIR))

from modules.classifier import classify_item
from modules.agent_memory import load_memory
from modules.agent_loop import make_plan, run_agent_loop
from modules.command_router import CommandRouter
from modules.config_loader import load_config
from modules.external_cli import list_external_tools, run_external_tool
from modules.insight_extractor import extract_insights
from modules.model_setup import configure_environment, find_profile, redact_secret_text
from modules.providers.registry import resolve_llm_connection
from modules.report_generator import generate_daily_report
from modules.search_engine import search_goldfish
from modules.scorer import score_item
from modules.setup_agent import SetupSession, configure_search_environment, find_search_provider
from modules.skill_router import select_skills
from modules.skill_loader import list_skills, load_skill
from modules.source_health import build_source_health_records
from modules.state_store import GoldfishState
from modules.web_researcher import generate_research_markdown, rule_based_synthesis
from modules.web_researcher import _jina_results_from_text, _search_provider_order, _tavily_results_from_payload


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

    def test_command_router_routes_search(self):
        routed = CommandRouter().route('/search MCP --limit 3', {"no_llm": True})
        self.assertEqual(routed.tool_name, "search")
        self.assertIn("MCP", routed.args["query"])
        self.assertEqual(routed.args["limit"], 3)

    def test_command_router_routes_research(self):
        routed = CommandRouter().route('/research MCP servers --limit 3 --no-llm', {"no_llm": True})
        self.assertEqual(routed.tool_name, "research_web")
        self.assertIn("MCP servers", routed.args["query"])
        self.assertEqual(routed.args["limit"], 3)
        self.assertTrue(routed.args["no_llm"])

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
        self.assertEqual(plan[0].tool, "research_web")
        self.assertEqual(plan[0].status, "search")
        self.assertTrue(plan[0].args["no_save"])

    def test_agent_loop_runs_with_fake_registry_and_workspace(self):
        class FakeRegistry:
            def __init__(self):
                self.calls = []

            def execute(self, name, args=None):
                self.calls.append((name, args or {}))
                if name == "research_web":
                    return {
                        "status": "ok",
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
        self.assertEqual(result["observations"][1]["tool"], "research_web")
        self.assertTrue(result["selected_skills"])

    def test_agent_loop_revises_plan_after_research_failure(self):
        class FakeRegistry:
            def execute(self, name, args=None):
                if name == "skills":
                    return {"status": "ok", "skill": {"name": (args or {}).get("name", "")}}
                if name == "research_web":
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
        self.assertEqual(result["observations"][1]["tool"], "research_web")
        self.assertEqual(result["observations"][2]["tool"], "search")
        self.assertIn("research_web_failed_add_local_search", result["plan_revisions"][1]["reason"])

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
        try:
            os.environ.pop("TAVILY_API_KEY", None)
            os.environ.pop("JINA_API_KEY", None)
            os.environ.pop("GOLDFISH_SEARCH_PROVIDER", None)
            self.assertEqual(_search_provider_order(), ["duckduckgo"])
            os.environ["JINA_API_KEY"] = "test-key"
            self.assertEqual(_search_provider_order()[0], "jina")
            os.environ["TAVILY_API_KEY"] = "test-key"
            self.assertEqual(_search_provider_order()[0], "tavily")
            self.assertEqual(_search_provider_order("jina")[0], "jina")
        finally:
            _restore_env("TAVILY_API_KEY", old_tavily)
            _restore_env("JINA_API_KEY", old_jina)
            _restore_env("GOLDFISH_SEARCH_PROVIDER", old_provider)

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

    def test_setup_search_noninteractive_does_not_prompt_for_key(self):
        old_tavily = os.environ.get("TAVILY_API_KEY")
        try:
            os.environ.pop("TAVILY_API_KEY", None)
            answer = SetupSession(interactive=False).handle("/search tavily")
            self.assertIn("requires `TAVILY_API_KEY`", answer)
            self.assertIn("goldfish setup", answer)
        finally:
            _restore_env("TAVILY_API_KEY", old_tavily)

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
        command = [sys.executable, str(AGENT_DIR / "cli.py"), "agent", "show tools", "--no-llm", "--max-steps", "1", "--no-save"]
        result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"agent"', result.stdout)
        self.assertIn('"task_id"', result.stdout)
        self.assertIn('"plan_execute"', result.stdout)

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
