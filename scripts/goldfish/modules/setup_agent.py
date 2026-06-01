"""Setup wizard for goldfish."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict

from . import cli_theme
from .config_loader import load_config
from .model_setup import configure_environment, find_profile, model_menu, prompt_for_api_key, set_user_environment_variable
from .tool_registry import DEFAULT_REGISTRY
from .utils import get_env


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SearchProviderProfile:
    key: str
    label: str
    env_key: str
    endpoint_env_key: str
    default_endpoint: str
    aliases: tuple[str, ...]
    requires_api_key: bool = True


LANGUAGE_PROFILES = (
    LanguageProfile("zh-CN", "Chinese (Simplified)", ("zh", "cn", "chinese", "simplified", "中文", "简体中文", "简体")),
    LanguageProfile("en", "English", ("english", "en-US", "en-us", "us")),
    LanguageProfile("ja", "Japanese", ("jp", "japanese", "日本語", "日语")),
    LanguageProfile("ko", "Korean", ("kr", "korean", "한국어", "韩语")),
)


SEARCH_PROVIDER_PROFILES = (
    SearchProviderProfile(
        key="tavily",
        label="Tavily Search API",
        env_key="TAVILY_API_KEY",
        endpoint_env_key="TAVILY_SEARCH_ENDPOINT",
        default_endpoint="https://api.tavily.com/search",
        aliases=("1", "tavily-search"),
    ),
    SearchProviderProfile(
        key="jina",
        label="Jina Search",
        env_key="JINA_API_KEY",
        endpoint_env_key="JINA_SEARCH_ENDPOINT",
        default_endpoint="https://s.jina.ai/",
        aliases=("2", "jina-search", "jina_ai"),
    ),
    SearchProviderProfile(
        key="news",
        label="Realtime News Chain",
        env_key="",
        endpoint_env_key="",
        default_endpoint="",
        aliases=("4", "latest", "realtime", "real-time", "news-search"),
        requires_api_key=False,
    ),
    SearchProviderProfile(
        key="hackernews",
        label="Hacker News Algolia",
        env_key="",
        endpoint_env_key="",
        default_endpoint="",
        aliases=("5", "hn", "hacker-news", "algolia"),
        requires_api_key=False,
    ),
    SearchProviderProfile(
        key="gdelt",
        label="GDELT DOC API",
        env_key="",
        endpoint_env_key="",
        default_endpoint="",
        aliases=("6", "gdelt-doc"),
        requires_api_key=False,
    ),
    SearchProviderProfile(
        key="duckduckgo",
        label="DuckDuckGo HTML fallback",
        env_key="",
        endpoint_env_key="",
        default_endpoint="",
        aliases=("3", "7", "ddg", "duck"),
        requires_api_key=False,
    ),
)


SETUP_HELP = """goldfish setup commands:

/model          Select a model and enter its API key
/model list     Show available model profiles
/search         Select a web search provider and enter its API key
/search list    Show available search providers
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
        if lower.startswith("/search"):
            return self._search(text)
        if lower.startswith("/language"):
            return self._language(text)
        return "Unknown setup command. Try /model, /search, /language, /doctor, help, or /exit."

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
        persist_model_settings(configured)
        return _setup_result(configured)

    def _search(self, command: str) -> str:
        parts = command.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        if arg.lower() in {"list", "ls", "help", "status"}:
            return search_provider_status() + "\n\n" + search_provider_menu()
        return self.configure_search_provider(arg)

    def configure_search_provider(self, arg: str = "") -> str:
        if not arg:
            if not self.interactive:
                return search_provider_status() + "\n\n" + search_provider_menu()
            print(search_provider_menu())
            arg = input(cli_theme.prompt("search")).strip()
            if not arg:
                return "Canceled: no search provider was selected."

        profile = find_search_provider(arg)
        if profile is None:
            return f"Unknown search provider: {arg}\n\n{search_provider_menu()}"

        if not profile.requires_api_key:
            configured = configure_search_environment(profile, api_key="", endpoint="", persist_user=True)
            return _search_setup_result(configured)

        existing = get_env(profile.env_key) or ""
        if not self.interactive:
            if existing:
                configured = configure_search_environment(profile, api_key=existing, endpoint="", persist_user=True)
                return _search_setup_result(configured)
            return (
                f"{profile.label} requires `{profile.env_key}`.\n"
                "Run `goldfish setup`, enter `/search`, choose this provider, then paste the API key.\n"
                "No API key is written to project files."
            )

        api_key = prompt_for_search_api_key(profile.env_key, hidden=self.hidden_key)
        if not api_key:
            return "Canceled: no API key was entered and no existing environment variable was found."
        endpoint_prompt = f"{profile.endpoint_env_key} [{profile.default_endpoint}]> "
        endpoint = input(endpoint_prompt).strip() or profile.default_endpoint
        configured = configure_search_environment(profile, api_key=api_key, endpoint=endpoint, persist_user=True)
        return _search_setup_result(configured)

    def _language(self, command: str) -> str:
        parts = command.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        if arg.lower() in {"list", "ls", "help"}:
            return _language_status() + "\n\n" + language_menu()
        if not arg:
            if not self.interactive:
                return _language_status() + "\n\n" + language_menu()
            print(language_menu())
            choice = input(cli_theme.prompt("language")).strip()
            if not choice:
                return "Canceled: no language was selected."
            return configure_language(choice)
        return configure_language(arg)


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


def search_provider_menu() -> str:
    current = get_env("GOLDFISH_SEARCH_PROVIDER", "auto")
    lines = ["Select the public web search provider goldfish should use:"]
    for index, profile in enumerate(SEARCH_PROVIDER_PROFILES, start=1):
        marker = "*" if profile.key == current else " "
        key_info = profile.env_key if profile.requires_api_key else "no API key"
        lines.append(f"{marker} {index}. {profile.label}  provider={profile.key}  env={key_info}")
    lines.extend(
        [
            "",
            "Recommended order: Tavily -> Jina -> DuckDuckGo. For real-time news, choose news.",
            "Enter a number or provider key.",
            "API keys are saved to user-level environment variables only.",
        ]
    )
    return "\n".join(lines)


def find_search_provider(choice: str) -> SearchProviderProfile | None:
    cleaned = (choice or "").strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    for profile in SEARCH_PROVIDER_PROFILES:
        if lowered in {profile.key.lower(), profile.label.lower(), *{alias.lower() for alias in profile.aliases}}:
            return profile
    return None


def configure_search_environment(
    profile: SearchProviderProfile,
    *,
    api_key: str = "",
    endpoint: str = "",
    persist_user: bool = False,
) -> Dict[str, str]:
    values = {"GOLDFISH_SEARCH_PROVIDER": profile.key}
    if profile.requires_api_key:
        values[profile.env_key] = api_key
        if endpoint or profile.default_endpoint:
            values[profile.endpoint_env_key] = endpoint or profile.default_endpoint

    for key, value in values.items():
        if value == "":
            continue
        os.environ[key] = value
        if persist_user:
            set_user_environment_variable(key, value)

    return {
        "provider": profile.key,
        "label": profile.label,
        "env_key": profile.env_key or "none",
        "endpoint_env_key": profile.endpoint_env_key or "none",
        "endpoint": endpoint or profile.default_endpoint,
        "api_key_saved": bool(profile.requires_api_key and api_key),
    }


def prompt_for_search_api_key(env_key: str, hidden: bool = False) -> str:
    existing = get_env(env_key) or ""
    suffix = ", press Enter to keep the current environment value" if existing else ""
    prompt = f"Enter {env_key}{suffix}: "
    if hidden:
        import getpass

        try:
            value = getpass.getpass(prompt).strip()
        except Exception:
            value = input(prompt).strip()
    else:
        print("Paste-friendly input is enabled. The key is not written to project files or logs, but it may be visible in this terminal.")
        value = input(prompt).strip()
    return value or existing


def search_provider_status() -> str:
    current = get_env("GOLDFISH_SEARCH_PROVIDER", "auto")
    tavily = "configured" if get_env("TAVILY_API_KEY") else "missing"
    jina = "configured" if (get_env("JINA_API_KEY") or get_env("JINA_SEARCH_API_KEY")) else "missing"
    return (
        "Current search provider configuration:\n"
        f"- GOLDFISH_SEARCH_PROVIDER: {current}\n"
        f"- TAVILY_API_KEY: {tavily}\n"
        f"- JINA_API_KEY/JINA_SEARCH_API_KEY: {jina}\n"
        "- Realtime News Chain: available without API key\n"
        "- Hacker News Algolia: available without API key\n"
        "- GDELT DOC API: available without API key\n"
        "- DuckDuckGo fallback: available without API key"
    )


def _search_setup_result(configured: Dict[str, str]) -> str:
    key_line = (
        f"- api_key_env: {configured['env_key']}\n"
        if configured.get("api_key_saved")
        else "- api_key_env: none required\n"
    )
    endpoint = configured.get("endpoint") or "default"
    return (
        "Search provider configuration saved.\n"
        f"- provider: {configured['provider']} ({configured['label']})\n"
        f"- endpoint: {endpoint}\n"
        f"{key_line}"
        "- API key was written to user-level environment variables only.\n"
        "- Next: goldfish doctor\n"
        "- Then: goldfish research \"MCP server commercial opportunities\""
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


def persist_model_settings(configured: Dict[str, Any]) -> None:
    config = load_config()
    settings = dict(config.settings)
    settings["llm_provider"] = configured["provider"]
    settings["llm_model"] = configured["model"]
    settings["llm_base_url"] = configured["base_url"]
    _write_json(config.config_dir / "settings.json", settings)


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
