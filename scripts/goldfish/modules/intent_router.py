"""Config-driven natural-language intent routing for goldfish."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .utils import agent_dir


@dataclass(frozen=True)
class IntentRoute:
    name: str
    tool_name: str
    args: Dict[str, Any]
    response_hint: str


def route_intent(message: str, defaults: Dict[str, Any] | None = None, *, config_path: Path | None = None) -> IntentRoute | None:
    text = (message or "").strip()
    if not text:
        return None
    defaults = defaults or {}
    config = _load_intent_config(config_path)
    matches = []
    for intent in config.get("intents", []):
        if not intent.get("enabled", True):
            continue
        score = _match_score(text, intent.get("match", {}))
        if score <= 0:
            continue
        matches.append((int(intent.get("priority", 0) or 0), score, intent))
    if not matches:
        return None
    _, _, intent = sorted(matches, key=lambda item: (item[0], item[1]), reverse=True)[0]
    args = dict(defaults)
    args.update(intent.get("args", {}) if isinstance(intent.get("args"), dict) else {})
    if intent.get("query_from_message"):
        args["query"] = _clean_query(text, intent.get("query_cleanup", []))
    if intent.get("goal_from_message"):
        args["goal"] = text
    for flag_rule in intent.get("set_flags_when_any", []):
        if not isinstance(flag_rule, dict):
            continue
        keywords = [str(item) for item in flag_rule.get("keywords", [])]
        if _contains_any(text, keywords):
            args.update(flag_rule.get("args", {}) if isinstance(flag_rule.get("args"), dict) else {})
    return IntentRoute(
        name=str(intent.get("name") or ""),
        tool_name=str(intent.get("tool") or ""),
        args=args,
        response_hint=str(intent.get("response_hint") or ""),
    )


def _load_intent_config(config_path: Path | None = None) -> Dict[str, Any]:
    path = config_path or agent_dir() / "config" / "tool_intents.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"intents": []}


def _match_score(text: str, match: Dict[str, Any]) -> int:
    lowered = text.lower()
    score = 0
    any_hits = [keyword for keyword in _strings(match.get("any")) if keyword.lower() in lowered]
    if any_hits:
        score += len(any_hits)
    required = _strings(match.get("all"))
    if required and not all(keyword.lower() in lowered for keyword in required):
        return 0
    score += len(required) * 2
    groups = match.get("all_any", [])
    if groups:
        for group in groups:
            hits = [keyword for keyword in _strings(group) if keyword.lower() in lowered]
            if not hits:
                return 0
            score += 2 + len(hits)
    return score


def _clean_query(text: str, cleanup: Any) -> str:
    query = text
    for marker in _strings(cleanup):
        query = query.replace(marker, "")
        query = query.replace(marker.title(), "")
    return query.strip(" ：:，,") or text.strip()


def _contains_any(text: str, keywords: List[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]
