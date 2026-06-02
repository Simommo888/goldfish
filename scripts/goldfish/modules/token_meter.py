"""Lightweight token and context telemetry for goldfish chat.

The numbers are intentionally transparent:
- provider usage is used when an OpenAI-compatible response exposes it;
- otherwise goldfish falls back to a local estimate so the CLI can always show
  context pressure and turn cost without requiring a tokenizer dependency.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


DEFAULT_CONTEXT_TOKENS = 128_000
MODEL_CONTEXT_HINTS = [
    ("gpt-4.1", 1_000_000),
    ("gpt-4o", 128_000),
    ("gpt-4", 128_000),
    ("deepseek", 128_000),
    ("claude", 200_000),
    ("gemini", 1_000_000),
]


@dataclass(frozen=True)
class TurnTokenStats:
    status: str
    model: str
    context_limit: int
    context_used: int
    context_remaining: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "model": self.model,
            "context_limit": self.context_limit,
            "context_used": self.context_used,
            "context_remaining": self.context_remaining,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated": self.estimated,
        }


def estimate_tokens(text: str) -> int:
    """Approximate mixed Chinese/English token count without extra deps."""

    if not text:
        return 0
    chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_\u4e00-\u9fff]", text))
    # Chinese text is often close to one token per 1-2 chars; English is roughly
    # 0.75 token per word plus punctuation. Bias slightly high for safety.
    return max(1, math.ceil(chinese_chars * 0.9 + ascii_words * 0.85))


def estimate_messages_tokens(messages: Iterable[Dict[str, str]]) -> int:
    total = 0
    for message in messages:
        total += 4
        total += estimate_tokens(str(message.get("role") or ""))
        total += estimate_tokens(str(message.get("content") or ""))
    return total + 2


def context_limit_for_model(model: str, settings: Dict[str, Any] | None = None) -> int:
    settings = settings or {}
    configured = settings.get("context_window_tokens") or settings.get("context_limit_tokens")
    try:
        if configured:
            return max(4_096, int(configured))
    except Exception:
        pass
    lowered = (model or "").lower()
    for marker, limit in MODEL_CONTEXT_HINTS:
        if marker in lowered:
            return limit
    return DEFAULT_CONTEXT_TOKENS


def build_turn_stats(
    *,
    status: str,
    model: str,
    context_limit: int,
    input_tokens: int,
    output_tokens: int = 0,
    provider_usage: Dict[str, Any] | None = None,
) -> TurnTokenStats:
    usage = provider_usage or {}
    prompt_tokens = _usage_int(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _usage_int(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_int(usage, "total_tokens")
    estimated = True
    if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
        estimated = False
        input_tokens = prompt_tokens if prompt_tokens is not None else input_tokens
        output_tokens = completion_tokens if completion_tokens is not None else output_tokens
        total_tokens = total_tokens if total_tokens is not None else input_tokens + output_tokens
    else:
        total_tokens = input_tokens + output_tokens
    context_used = max(0, input_tokens + output_tokens)
    return TurnTokenStats(
        status=status,
        model=model or "unknown",
        context_limit=context_limit,
        context_used=context_used,
        context_remaining=max(0, context_limit - context_used),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated=estimated,
    )


def render_turn_stats(stats: TurnTokenStats, *, color: bool = False) -> str:
    prefix = "~" if stats.estimated else "="
    return (
        f"><(((o> status={stats.status}  "
        f"context={context_energy_bar(stats.context_remaining, stats.context_limit)}  "
        f"tokens={prefix}{_compact(stats.total_tokens)} "
        f"(in={prefix}{_compact(stats.input_tokens)}, out={prefix}{_compact(stats.output_tokens)})"
    )


def context_energy_bar(context_remaining: int, context_limit: int, *, width: int = 14) -> str:
    limit = max(1, int(context_limit or DEFAULT_CONTEXT_TOKENS))
    remaining = max(0, min(limit, int(context_remaining or 0)))
    ratio = remaining / limit
    filled = max(0, min(width, round(ratio * width)))
    empty = width - filled
    percent = max(0, min(100, round(ratio * 100)))
    filled_char = "\u2588"
    empty_char = "\u2591"
    return f"[{filled_char * filled}{empty_char * empty}] {percent:3d}%"


def context_remaining_from_used(context_used: int, context_limit: int) -> int:
    return max(0, int(context_limit or DEFAULT_CONTEXT_TOKENS) - max(0, int(context_used or 0)))


def history_tokens(history: List[Dict[str, str]], *, keep_last: int = 12) -> int:
    return estimate_messages_tokens(history[-keep_last:])


def _usage_int(usage: Dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        try:
            if value is not None:
                return int(value)
        except Exception:
            continue
    return None


def _compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)
