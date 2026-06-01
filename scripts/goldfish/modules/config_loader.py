"""Configuration loader for JSON config files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .utils import agent_dir


class ConfigError(RuntimeError):
    """Raised when a config file exists but cannot be parsed."""


@dataclass
class AgentConfig:
    sources: Dict[str, Any]
    people: Dict[str, Any]
    keywords: Dict[str, Any]
    settings: Dict[str, Any]
    llm_prompts: Dict[str, Any]
    agent_profile: Dict[str, Any]
    config_dir: Path


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        print(f"[goldfish] 配置文件不存在，使用默认空配置：{path}")
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON 格式错误：{path}，第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}") from exc


def load_config(config_dir: Path | None = None) -> AgentConfig:
    config_dir = config_dir or agent_dir() / "config"
    return AgentConfig(
        sources=load_json_file(config_dir / "sources.json", {}),
        people=load_json_file(config_dir / "people.json", {"people": []}),
        keywords=load_json_file(config_dir / "keywords.json", {}),
        settings=load_json_file(config_dir / "settings.json", {}),
        llm_prompts=load_json_file(config_dir / "llm_prompts.json", {}),
        agent_profile=load_json_file(config_dir / "agent_profile.json", {}),
        config_dir=config_dir,
    )


def flatten_sources(sources_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for category, entries in sources_config.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            merged = dict(entry)
            merged.setdefault("category", category)
            sources.append(merged)
    return sources


def enabled_sources(sources_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [source for source in flatten_sources(sources_config) if source.get("enabled", True)]


def sources_by_category(sources_config: Dict[str, Any], category: str) -> List[Dict[str, Any]]:
    return [source for source in enabled_sources(sources_config) if source.get("category") == category]


def enabled_people(people_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    people = people_config.get("people", [])
    if not isinstance(people, list):
        return []
    return [person for person in people if isinstance(person, dict) and person.get("enabled", True)]
