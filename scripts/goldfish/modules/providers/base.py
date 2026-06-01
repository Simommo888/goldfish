"""Provider interfaces used by goldfish.

The provider layer owns model API details. Agent workflows call this interface
instead of importing provider SDKs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str
    api_key: str


class LLMProvider(Protocol):
    config: ProviderConfig

    def generate_text(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        ...

    def generate_json(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, Any]:
        ...
