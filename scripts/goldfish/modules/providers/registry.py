"""Provider registry and environment-based credential resolution."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

from .base import ProviderConfig, LLMProvider
from .openai_compatible import OpenAICompatibleProvider


OPENAI_COMPATIBLE_PROVIDERS = {"openai", "deepseek", "openai-compatible", "compatible"}


def resolve_llm_connection(settings: Dict[str, Any]) -> Dict[str, str]:
    """Resolve provider, model, base URL, and API key from settings/env.

    API keys are read only from environment variables, never from config files.
    Priority: AI_NEWS_LLM_API_KEY > provider-specific key > OPENAI_API_KEY.
    """

    provider = str(_get_env("AI_NEWS_LLM_PROVIDER") or settings.get("llm_provider") or "openai").lower()
    model = _get_env("AI_NEWS_LLM_MODEL") or str(settings.get("llm_model") or "gpt-4.1-mini")
    base_url = _get_env("AI_NEWS_LLM_BASE_URL") or str(settings.get("llm_base_url") or "")
    api_key = _get_env("AI_NEWS_LLM_API_KEY") or ""

    if not api_key and provider == "deepseek":
        api_key = _get_env("DEEPSEEK_API_KEY") or ""
        base_url = base_url or "https://api.deepseek.com"
    if not api_key and provider == "openai":
        api_key = _get_env("OPENAI_API_KEY") or ""
    if not api_key:
        api_key = _get_env("OPENAI_API_KEY") or ""

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
    }


def get_provider(settings: Dict[str, Any]) -> LLMProvider:
    connection = resolve_llm_connection(settings)
    provider = connection["provider"]
    if provider not in OPENAI_COMPATIBLE_PROVIDERS:
        raise RuntimeError(f"暂不支持的 LLM provider：{provider}")
    return OpenAICompatibleProvider(
        ProviderConfig(
            provider=provider,
            model=connection["model"],
            base_url=connection["base_url"],
            api_key=connection["api_key"],
        )
    )


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    if sys.platform.startswith("win"):
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                stored, _ = winreg.QueryValueEx(key, name)
                return str(stored or "")
        except Exception:
            return ""
    return ""
