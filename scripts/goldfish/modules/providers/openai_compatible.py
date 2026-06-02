"""OpenAI-compatible provider transport."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .base import ProviderConfig


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.last_usage: Dict[str, Any] = {}

    def _client(self):
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"openai 包不可用，请安装 requirements.txt 或使用 --no-llm：{exc}") from exc
        if not self.config.api_key:
            raise RuntimeError("未设置模型 API Key，已降级为规则摘要。")
        return OpenAI(api_key=self.config.api_key, base_url=self.config.base_url or None, timeout=45)

    def generate_text(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        response = self._client().chat.completions.create(
            model=self.config.model,
            temperature=temperature,
            messages=messages,
        )
        self.last_usage = _usage_to_dict(getattr(response, "usage", None))
        return response.choices[0].message.content or ""

    def generate_json(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, Any]:
        text = self.generate_text(messages, temperature=temperature)
        return _parse_json_object(text)


def _parse_json_object(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.S | re.I)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"模型未返回合法 JSON：{exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("模型 JSON 输出不是对象。")
    return parsed


def _usage_to_dict(usage: Any) -> Dict[str, Any]:
    if not usage:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        try:
            dumped = usage.model_dump()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            pass
    result: Dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = value
    return result
