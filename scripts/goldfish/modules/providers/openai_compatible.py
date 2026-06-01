"""OpenAI-compatible provider transport."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .base import ProviderConfig


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

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
