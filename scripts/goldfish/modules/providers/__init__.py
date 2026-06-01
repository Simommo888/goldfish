"""LLM provider abstractions for goldfish."""

from .registry import get_provider, resolve_llm_connection

__all__ = ["get_provider", "resolve_llm_connection"]
