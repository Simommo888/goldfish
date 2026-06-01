"""Conversational REPL for the goldfish intelligence agent."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from . import cli_theme
from .command_router import CommandRouter, HELP_TEXT
from .config_loader import load_config
from .model_setup import redact_secret_text
from .providers.registry import get_provider, resolve_llm_connection
from .state_store import GoldfishState
from .startup_page import print_startup_banner
from .tool_registry import DEFAULT_REGISTRY
from .utils import kb_root, now


LLM_LANGUAGE_NAMES = {
    "zh-CN": "Simplified Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
}


class ChatSession:
    """Small conversational shell around the goldfish tool registry."""

    def __init__(
        self,
        use_llm: bool = True,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        interactive: bool = False,
    ) -> None:
        self.root = kb_root()
        self.config = load_config()
        self.use_llm = use_llm
        self.output_language = str(self.config.settings.get("output_language") or "zh-CN")
        self.provider = provider or self.config.settings.get("llm_provider", "deepseek")
        settings = dict(self.config.settings)
        settings["llm_provider"] = self.provider
        if model:
            settings["llm_model"] = model
        if base_url:
            settings["llm_base_url"] = base_url
        connection = resolve_llm_connection(settings)
        self.model = connection["model"]
        self.base_url = connection["base_url"]
        self.history: List[Dict[str, str]] = []
        self.interactive = interactive
        self.session_id = now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        self.state = GoldfishState(self.root)
        self.router = CommandRouter()

    def session_defaults(self) -> Dict[str, Any]:
        return {
            "no_llm": not self.use_llm,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "emit_report": False,
        }

    def status(self) -> Dict[str, Any]:
        tools = DEFAULT_REGISTRY.list_tools()
        return {
            "provider": self.provider,
            "model": self.model,
            "tools": len(tools),
            "tool_list": [
                {
                    "name": str(tool.get("name", "")),
                    "description": str(tool.get("description", "")),
                }
                for tool in tools
            ],
            "memory": "on",
            "status": "ready",
            "workspace": str(self.root),
            "session": self.session_id,
            "recent_sessions": self._recent_sessions(),
        }

    def _recent_sessions(self) -> List[Dict[str, str]]:
        sessions: List[Dict[str, str]] = []
        try:
            for row in self.state.recent_message_sessions(limit=3):
                session_id = str(row.get("session_id") or "")
                if not session_id:
                    continue
                sessions.append(
                    {
                        "name": _short_session_name(session_id),
                        "time": _relative_time(str(row.get("last_seen") or "")),
                    }
                )
        except Exception:
            return []
        return sessions

    def _remember_turn(self, role: str, content: str) -> None:
        safe_content = redact_secret_text(content)
        self.history.append({"role": role, "content": safe_content})
        history_path = self.root / "scripts" / "goldfish" / "output_cache" / "chat_history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"time": now().isoformat(), "session_id": self.session_id, "role": role, "content": safe_content}
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.state.record_message(self.session_id, role, safe_content)

    def respond(self, message: str) -> str:
        message = message.strip()
        self._remember_turn("user", message)

        if not message:
            answer = "I am here. Try `/research <query>`, `/tools`, `/doctor`, or `/run --write-drafts`."
            self._remember_turn("assistant", answer)
            return answer

        session_answer = self._handle_session_command(message)
        if session_answer:
            self._remember_turn("assistant", session_answer)
            return session_answer

        local_answer = self._local_answer(message)
        if local_answer:
            self._remember_turn("assistant", local_answer)
            return local_answer

        routed = self.router.route(message, self.session_defaults())
        if routed.exit_requested:
            self._remember_turn("assistant", "__EXIT__")
            return "__EXIT__"

        if self.interactive and routed.tool_name and not routed.unknown:
            print(cli_theme.status("run", routed.tool_name), flush=True)
        routed_answer = self.router.execute(routed)
        if routed_answer:
            self._remember_turn("assistant", routed_answer)
            return routed_answer

        if self.interactive and self.use_llm:
            print(cli_theme.thinking(), flush=True)
        llm_answer = self._llm_answer(message)
        if not llm_answer:
            llm_answer = (
                "I could not map that to a local action yet. Try `/tools`, `/research <query>`, "
                "`/dry`, `/run`, `/weekly`, or `/history`."
            )
        self._remember_turn("assistant", llm_answer)
        return llm_answer

    def _handle_session_command(self, message: str) -> str:
        lower = message.lower()
        if lower in {"help", "/help"}:
            return HELP_TEXT
        if lower.startswith("/model"):
            return "Use `goldfish setup`, then enter `/model` to configure the model and API key."
        if lower.startswith("/provider "):
            self.provider = message.split(" ", 1)[1].strip()
            return f"Provider for this chat session: {self.provider}"
        if lower.startswith("/base-url "):
            self.base_url = message.split(" ", 1)[1].strip()
            return f"Base URL for this chat session: {self.base_url}"
        if lower == "/llm":
            self.use_llm = True
            return f"LLM replies enabled. Current model: {self.model}"
        if lower == "/no-llm":
            self.use_llm = False
            return "LLM replies disabled. This session will use local routing and rule summaries."
        return ""

    def _local_answer(self, message: str) -> str:
        lower = message.lower().strip()
        if lower and set(lower) <= {"?", "？", " "}:
            return "I received an empty or garbled question. Try `help`, `exit`, `/tools`, or `/doctor`."
        if lower in {"hi", "hello", "hey", "你好", "您好"}:
            return (
                "Hello, I am goldfish. I can research public sources, generate AI intelligence reports, "
                "draft permanent notes, business ideas, prompts, and project ideas, then save them into Obsidian."
            )
        if lower in {"你是谁", "你能做什么", "介绍一下", "who are you", "what can you do"}:
            return (
                "I am goldfish, a local AI intelligence and knowledge-deposition agent. "
                "I can run daily and weekly reports, search local history, research public web pages, "
                "and use a configured OpenAI-compatible model through `goldfish setup`."
            )
        return ""

    def _llm_answer(self, message: str) -> str:
        settings = dict(self.config.settings)
        settings["llm_provider"] = self.provider
        settings["llm_model"] = self.model
        settings["llm_base_url"] = self.base_url
        connection = resolve_llm_connection(settings)
        if not self.use_llm or not connection["api_key"]:
            return ""

        prompt = (
            "You are goldfish, the CLI conversation layer for a local AI intelligence "
            "and knowledge-deposition agent. Explain usage, configuration, workflows, "
            "safety boundaries, and next actions. Do not claim a command has run unless "
            "the local tool router ran it. Do not invent sources, person opinions, or API keys. "
            f"Reply in {self._llm_language_name()} unless the user explicitly asks for another language."
        )
        try:
            return get_provider(settings).generate_text(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.2,
            )
        except Exception:
            return ""

    def _llm_language_name(self) -> str:
        return LLM_LANGUAGE_NAMES.get(self.output_language, self.output_language)


def run_chat(
    once: str | None = None,
    use_llm: bool = True,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> int:
    _prefer_utf8_terminal()
    session = ChatSession(use_llm=use_llm, provider=provider, model=model, base_url=base_url, interactive=once is None)
    if once is not None:
        answer = session.respond(once)
        if answer != "__EXIT__":
            print(answer)
        return 0

    print_startup_banner(session.status())
    while True:
        try:
            message = input(cli_theme.prompt())
        except (EOFError, KeyboardInterrupt):
            print("\n" + cli_theme.farewell())
            return 0
        answer = session.respond(message)
        if answer == "__EXIT__":
            print(cli_theme.farewell())
            return 0
        print(answer)


def _prefer_utf8_terminal() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _short_session_name(session_id: str) -> str:
    if "-" in session_id:
        prefix, suffix = session_id.split("-", 1)
        if len(prefix) >= 8 and suffix:
            return f"chat-{prefix[-4:]}-{suffix[:4]}"
    return session_id[:18] or "session"


def _relative_time(value: str) -> str:
    if not value:
        return "new"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        delta = now() - dt
        seconds = max(0, int(delta.total_seconds()))
        if seconds < 60:
            return "now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return value[:10]
