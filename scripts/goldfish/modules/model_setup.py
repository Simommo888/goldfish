"""Interactive model setup helpers for goldfish chat."""

from __future__ import annotations

import getpass
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ModelProfile:
    key: str
    label: str
    provider: str
    model: str
    base_url: str
    env_key: str


MODEL_PROFILES: List[ModelProfile] = [
    ModelProfile(
        key="deepseek-v4-pro",
        label="DeepSeek V4 Pro",
        provider="deepseek",
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
    ),
    ModelProfile(
        key="deepseek-chat",
        label="DeepSeek Chat",
        provider="deepseek",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
    ),
    ModelProfile(
        key="openai-gpt-4.1-mini",
        label="OpenAI GPT-4.1 Mini",
        provider="openai",
        model="gpt-4.1-mini",
        base_url="",
        env_key="OPENAI_API_KEY",
    ),
    ModelProfile(
        key="custom",
        label="Custom OpenAI-compatible API",
        provider="openai-compatible",
        model="",
        base_url="",
        env_key="AI_NEWS_LLM_API_KEY",
    ),
]


def model_menu() -> str:
    lines = ["Select the model goldfish should use:"]
    for index, profile in enumerate(MODEL_PROFILES, start=1):
        model = profile.model or "custom"
        base_url = profile.base_url or "default"
        lines.append(f"{index}. {profile.label}  provider={profile.provider}  model={model}  base_url={base_url}")
    lines.append("")
    lines.append("Enter a number, profile key, or press Enter for 1.")
    return "\n".join(lines)


def find_profile(choice: str) -> ModelProfile:
    cleaned = (choice or "").strip()
    if not cleaned:
        return MODEL_PROFILES[0]
    if cleaned.isdigit():
        index = int(cleaned)
        if 1 <= index <= len(MODEL_PROFILES):
            return MODEL_PROFILES[index - 1]
    lowered = cleaned.lower()
    for profile in MODEL_PROFILES:
        if lowered in {profile.key.lower(), profile.label.lower(), profile.provider.lower(), profile.model.lower()}:
            return profile
    return MODEL_PROFILES[0]


def configure_environment(
    profile: ModelProfile,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
    provider: str | None = None,
    persist_user: bool = False,
) -> Dict[str, str]:
    selected_provider = provider or profile.provider
    selected_model = model or profile.model
    selected_base_url = base_url if base_url is not None else profile.base_url
    values = {
        "AI_NEWS_LLM_PROVIDER": selected_provider,
        "AI_NEWS_LLM_MODEL": selected_model,
        "AI_NEWS_LLM_BASE_URL": selected_base_url,
        profile.env_key: api_key,
        "AI_NEWS_LLM_API_KEY": api_key,
    }
    for key, value in values.items():
        os.environ[key] = value
        if persist_user:
            set_user_environment_variable(key, value)
    return {
        "provider": selected_provider,
        "model": selected_model,
        "base_url": selected_base_url,
        "env_key": profile.env_key,
    }


def prompt_for_api_key(env_key: str, hidden: bool = False) -> str:
    existing = os.getenv(env_key) or os.getenv("AI_NEWS_LLM_API_KEY") or ""
    suffix = ", press Enter to keep the current environment value" if existing else ""
    prompt = f"Enter {env_key}{suffix}: "
    if hidden:
        try:
            value = getpass.getpass(prompt).strip()
        except Exception:
            value = input(prompt).strip()
    else:
        print("Paste-friendly input is enabled. The key is not written to project files or logs, but it may be visible in this terminal.")
        value = input(prompt).strip()
    return value or existing


def set_user_environment_variable(name: str, value: str) -> None:
    """Persist an environment variable for future shells without touching repo files."""

    if sys.platform.startswith("win"):
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
        return
    shell_profile = os.path.expanduser("~/.goldfish_env")
    line = f'export {name}="{value}"\n'
    existing = ""
    if os.path.exists(shell_profile):
        with open(shell_profile, "r", encoding="utf-8") as handle:
            existing = handle.read()
    pattern = re.compile(rf"^export {re.escape(name)}=.*$", re.M)
    updated = pattern.sub(line.strip(), existing) if pattern.search(existing) else existing + line
    with open(shell_profile, "w", encoding="utf-8") as handle:
        handle.write(updated)


def redact_secret_text(text: str) -> str:
    patterns = [
        r"sk-[A-Za-z0-9_\-]{12,}",
        r"sk_[A-Za-z0-9_\-]{12,}",
        r"(?i)(api[_-]?key\s*[:=]\s*)[A-Za-z0-9_\-]{12,}",
    ]
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, lambda match: match.group(1) + "***REDACTED***" if match.groups() else "***REDACTED***", redacted)
    return redacted
