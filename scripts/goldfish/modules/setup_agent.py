"""Setup wizard for goldfish."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict

from . import cli_theme
from .config_loader import load_config
from .model_setup import configure_environment, find_profile, model_menu, prompt_for_api_key
from .tool_registry import DEFAULT_REGISTRY


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    label: str
    aliases: tuple[str, ...]


LANGUAGE_PROFILES = (
    LanguageProfile("zh-CN", "Chinese (Simplified)", ("zh", "cn", "chinese", "simplified", "中文", "简体中文", "简体")),
    LanguageProfile("en", "English", ("english", "en-US", "en-us", "us")),
    LanguageProfile("ja", "Japanese", ("jp", "japanese", "日本語", "日语")),
    LanguageProfile("ko", "Korean", ("kr", "korean", "한국어", "韩语")),
)


SETUP_HELP = """goldfish setup commands:

/model          Select a model and enter its API key
/model list     Show available model profiles
/language       Choose output language
/doctor         Check current runtime and model configuration
/exit           Leave setup

Safety:
- API keys are saved to user-level environment variables, not project files.
- On Windows, goldfish writes HKCU\\Environment and reads it directly.
- Do not paste API keys into normal chat, Markdown, or JSON config.
"""


def run_setup(once: str | None = None) -> int:
    _prefer_utf8_terminal()
    session = SetupSession(interactive=once is None)
    if once is not None:
        answer = session.handle(once)
        if answer != "__EXIT__":
            print(answer)
        return 0

    print(cli_theme.setup_banner())
    while True:
        try:
            message = input(cli_theme.prompt("setup")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n" + cli_theme.farewell())
            return 0
        answer = session.handle(message)
        if answer == "__EXIT__":
            print(cli_theme.farewell())
            return 0
        print(answer)


class SetupSession:
    def __init__(self, hidden_key: bool = False, interactive: bool = False) -> None:
        self.hidden_key = hidden_key
        self.interactive = interactive

    def handle(self, message: str) -> str:
        text = (message or "").strip()
        lower = text.lower()
        if not text or lower in {"help", "/help"}:
            return SETUP_HELP
        if lower in {"/exit", "exit", "quit", "q"}:
            return "__EXIT__"
        if lower in {"/doctor", "doctor"}:
            return json.dumps(DEFAULT_REGISTRY.execute("doctor"), ensure_ascii=False, indent=2)
        if lower.startswith("/model"):
            return self._model(text)
        if lower.startswith("/language"):
            return self._language(text)
        return "Unknown setup command. Try /model, /language, /doctor, help, or /exit."

    def _model(self, command: str) -> str:
        parts = command.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        if arg.lower() in {"list", "ls", "help"}:
            return model_menu()
        return self.configure_model(arg)

    def configure_model(self, arg: str = "") -> str:
        print(model_menu())
        profile = find_profile(arg or input(cli_theme.prompt("model")).strip())
        provider = profile.provider
        model = profile.model
        base_url = profile.base_url

        if profile.key == "custom":
            provider = input("provider [openai-compatible]> ").strip() or "openai-compatible"
            model = input("model> ").strip()
            base_url = input("base_url> ").strip()
            if not model:
                return "Canceled: custom model requires a model name."

        api_key = prompt_for_api_key(profile.env_key, hidden=self.hidden_key)
        if not api_key:
            return "Canceled: no API key was entered and no existing environment variable was found."

        configured = configure_environment(profile, api_key, model=model, base_url=base_url, provider=provider, persist_user=True)
        return _setup_result(configured)

    def _language(self, command: str) -> str:
        parts = command.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        if not arg:
            if not self.interactive:
                return _language_status() + "\n\n" + language_menu()
            print(language_menu())
            choice = input(cli_theme.prompt("language")).strip()
            if not choice:
                return "Canceled: no language was selected."
            return configure_language(choice)
        return "Language changes must be made from the interactive /language menu. Run goldfish setup, then enter /language."


def _setup_result(configured: Dict[str, Any]) -> str:
    return (
        "Model configuration saved.\n"
        f"- provider: {configured['provider']}\n"
        f"- model: {configured['model']}\n"
        f"- base_url: {configured['base_url'] or 'default'}\n"
        f"- api_key_env: {configured['env_key']} / AI_NEWS_LLM_API_KEY\n"
        "- API key was written to user-level environment variables only.\n"
        "- Next: goldfish doctor\n"
        "- Then: goldfish run"
    )


def language_menu() -> str:
    current = _current_language()
    lines = ["Available output languages:"]
    for index, profile in enumerate(LANGUAGE_PROFILES, start=1):
        marker = "*" if profile.code == current else " "
        aliases = ", ".join(_ascii_aliases(profile)[:3])
        lines.append(f"{marker} {index}. {profile.code:<6} {profile.label}  ({aliases})")
    lines.extend(
        [
            "",
            "Usage:",
            "- Run goldfish setup",
            "- Enter /language",
            "- Choose a number from the menu",
        ]
    )
    return "\n".join(lines)


def configure_language(value: str) -> str:
    profile = _find_language(value)
    if profile is None:
        return f"Unknown language: {value}\n\n{language_menu()}"

    config = load_config()
    settings = dict(config.settings)
    previous = str(settings.get("output_language") or "zh-CN")
    settings["output_language"] = profile.code
    _write_json(config.config_dir / "settings.json", settings)
    return (
        "Language configuration saved.\n"
        f"- previous: {previous}\n"
        f"- output_language: {profile.code} ({profile.label})\n"
        "- Next generated reports and summaries will use this language."
    )


def _language_status() -> str:
    current = _current_language()
    profile = _find_language(current)
    label = profile.label if profile else "Custom"
    return (
        "Current output language:\n"
        f"- output_language: {current} ({label})\n\n"
        "Use /language list to see options, or /language <code> to switch."
    )


def _current_language() -> str:
    return str(load_config().settings.get("output_language") or "zh-CN")


def _find_language(value: str) -> LanguageProfile | None:
    needle = value.strip().lower()
    if needle.isdigit():
        index = int(needle)
        if 1 <= index <= len(LANGUAGE_PROFILES):
            return LANGUAGE_PROFILES[index - 1]
    for profile in LANGUAGE_PROFILES:
        if needle == profile.code.lower() or needle in {alias.lower() for alias in profile.aliases}:
            return profile
    return None


def _write_json(path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ascii_aliases(profile: LanguageProfile) -> list[str]:
    return [alias for alias in profile.aliases if alias.isascii()]


def _prefer_utf8_terminal() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
