"""HTTP client for a local RAG knowledge-base service.

goldfish treats RAG as a bounded local knowledge tool: it calls configured
HTTP endpoints, never reads service internals directly, and never sends API
keys. If the service is unavailable, callers receive a structured degraded
result instead of an exception.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

from .config_loader import load_json_file
from .utils import agent_dir


JsonTransport = Callable[[str, str, Dict[str, Any] | None, int], Dict[str, Any]]


@dataclass(frozen=True)
class RagConfig:
    enabled: bool
    base_url: str
    health_endpoint: str
    stats_endpoint: str
    ask_endpoint: str
    search_endpoint: str
    retrieval_mode: str
    top_k: int
    use_llm: bool
    timeout_seconds: int
    config_path: Path


def load_rag_config(config_path: Path | None = None) -> RagConfig:
    path = config_path or agent_dir() / "config" / "rag.json"
    raw = load_json_file(
        path,
        {
            "enabled": False,
            "base_url": "http://127.0.0.1:8020",
            "health_endpoint": "/api/health",
            "stats_endpoint": "/api/rag/stats",
            "ask_endpoint": "/api/rag/ask",
            "search_endpoint": "/api/rag/search",
            "retrieval_mode": "hybrid",
            "top_k": 8,
            "use_llm": False,
            "timeout_seconds": 20,
        },
    )
    base_url = str(os.getenv("GOLDFISH_RAG_BASE_URL") or raw.get("base_url") or "http://127.0.0.1:8020").rstrip("/")
    return RagConfig(
        enabled=bool(raw.get("enabled", False)),
        base_url=base_url,
        health_endpoint=_endpoint(raw.get("health_endpoint"), "/api/health"),
        stats_endpoint=_endpoint(raw.get("stats_endpoint"), "/api/rag/stats"),
        ask_endpoint=_endpoint(raw.get("ask_endpoint"), "/api/rag/ask"),
        search_endpoint=_endpoint(raw.get("search_endpoint"), "/api/rag/search"),
        retrieval_mode=str(raw.get("retrieval_mode") or "hybrid"),
        top_k=_int(raw.get("top_k"), 8, 1, 30),
        use_llm=bool(raw.get("use_llm", False)),
        timeout_seconds=_int(raw.get("timeout_seconds"), 20, 3, 120),
        config_path=path,
    )


def rag_status(*, transport: JsonTransport | None = None, config: RagConfig | None = None) -> Dict[str, Any]:
    cfg = config or load_rag_config()
    if not cfg.enabled:
        return _disabled(cfg)
    transport = transport or _http_json
    health = _safe_request("GET", _url(cfg, cfg.health_endpoint), None, cfg.timeout_seconds, transport)
    stats = _safe_request("GET", _url(cfg, cfg.stats_endpoint), None, cfg.timeout_seconds, transport)
    ok = health.get("status") == "ok" and stats.get("status") == "ok"
    return {
        "status": "ok" if ok else "error",
        "error_type": "" if ok else _status_error_type(health, stats),
        "error": "" if ok else _status_error_text(health, stats),
        "enabled": cfg.enabled,
        "base_url": cfg.base_url,
        "health": health,
        "stats": stats,
        "config_path": str(cfg.config_path),
        "safety": _safety(),
    }


def rag_query(
    question: str,
    *,
    top_k: int | None = None,
    retrieval_mode: str | None = None,
    category: str = "all",
    use_llm: bool | None = None,
    transport: JsonTransport | None = None,
    config: RagConfig | None = None,
) -> Dict[str, Any]:
    cfg = config or load_rag_config()
    clean_question = str(question or "").strip()
    if not clean_question:
        return _empty_error("question", cfg, mode="rag_query")
    if not cfg.enabled:
        return _disabled(cfg, query=clean_question)
    payload = {
        "question": clean_question,
        "category": category or "all",
        "top_k": _int(top_k, cfg.top_k, 1, 20),
        "retrieval_mode": retrieval_mode or cfg.retrieval_mode,
        "use_llm": cfg.use_llm if use_llm is None else bool(use_llm),
    }
    transport = transport or _http_json
    response = _safe_request("POST", _url(cfg, cfg.ask_endpoint), payload, cfg.timeout_seconds, transport)
    if response.get("status") != "ok":
        return {
            "status": "error",
            "mode": "rag_query",
            "question": clean_question,
            "error": response.get("error", "RAG query failed"),
            "error_type": response.get("error_type", "retrieval_failed"),
            "request": payload,
            "sources": [],
            "source_count": 0,
            "base_url": cfg.base_url,
            "config_path": str(cfg.config_path),
            "safety": _safety(),
        }
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    sources = _normalize_sources(data.get("sources") or data.get("results"))
    return {
        "status": "ok",
        "mode": "rag_query",
        "question": clean_question,
        "answer": str(data.get("answer") or ""),
        "sources": sources,
        "source_count": len(sources),
        "llm_used": bool(data.get("llm_used", False)),
        "model": str(data.get("model") or ""),
        "warnings": [str(item) for item in data.get("warnings", [])] if isinstance(data.get("warnings"), list) else [],
        "request": payload,
        "base_url": cfg.base_url,
        "config_path": str(cfg.config_path),
        "safety": _safety(),
    }


def rag_search(
    query: str,
    *,
    top_k: int | None = None,
    retrieval_mode: str | None = None,
    category: str = "all",
    transport: JsonTransport | None = None,
    config: RagConfig | None = None,
) -> Dict[str, Any]:
    cfg = config or load_rag_config()
    clean_query = str(query or "").strip()
    if not clean_query:
        return _empty_error("query", cfg, mode="rag_search")
    if not cfg.enabled:
        return _disabled(cfg, query=clean_query)
    payload = {
        "query": clean_query,
        "category": category or "all",
        "top_k": _int(top_k, cfg.top_k, 1, 30),
        "retrieval_mode": retrieval_mode or cfg.retrieval_mode,
    }
    transport = transport or _http_json
    response = _safe_request("POST", _url(cfg, cfg.search_endpoint), payload, cfg.timeout_seconds, transport)
    if response.get("status") != "ok":
        return {
            "status": "error",
            "mode": "rag_search",
            "query": clean_query,
            "error": response.get("error", "RAG search failed"),
            "error_type": response.get("error_type", "retrieval_failed"),
            "request": payload,
            "results": [],
            "result_count": 0,
            "base_url": cfg.base_url,
            "config_path": str(cfg.config_path),
            "safety": _safety(),
        }
    data = response.get("data")
    if isinstance(data, dict):
        data = data.get("results") or data.get("sources") or data.get("matches") or []
    results = _normalize_sources(data)
    return {
        "status": "ok",
        "mode": "rag_search",
        "query": clean_query,
        "results": results,
        "result_count": len(results),
        "request": payload,
        "base_url": cfg.base_url,
        "config_path": str(cfg.config_path),
        "safety": _safety(),
    }


def _http_json(method: str, url: str, payload: Dict[str, Any] | None, timeout: int) -> Dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method.upper(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    return json.loads(text) if text.strip() else {}


def _safe_request(method: str, url: str, payload: Dict[str, Any] | None, timeout: int, transport: JsonTransport) -> Dict[str, Any]:
    try:
        return {"status": "ok", "data": transport(method, url, payload, timeout)}
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        return {"status": "error", "error_type": "http_error", "error": f"HTTP {exc.code}: {detail}", "url": url, "method": method, "timeout_seconds": timeout}
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if _is_timeout(reason):
            return {"status": "error", "error_type": "timeout", "error": f"RAG request timed out after {timeout}s", "url": url, "method": method, "timeout_seconds": timeout}
        return {"status": "error", "error_type": "service_unavailable", "error": str(reason), "url": url, "method": method, "timeout_seconds": timeout}
    except (TimeoutError, socket.timeout) as exc:
        return {"status": "error", "error_type": "timeout", "error": f"RAG request timed out after {timeout}s: {exc}", "url": url, "method": method, "timeout_seconds": timeout}
    except Exception as exc:
        return {"status": "error", "error_type": "retrieval_failed", "error": str(exc), "url": url, "method": method, "timeout_seconds": timeout}


def _normalize_sources(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": str(item.get("title") or item.get("file_path") or "Untitled"),
                "file_path": str(item.get("file_path") or ""),
                "heading": str(item.get("heading") or ""),
                "content": str(item.get("content") or ""),
                "score": item.get("score", 0),
                "keyword_score": item.get("keyword_score", 0),
                "vector_score": item.get("vector_score", 0),
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
            }
        )
    return normalized


def _disabled(cfg: RagConfig, *, query: str = "") -> Dict[str, Any]:
    return {
        "status": "error",
        "mode": "rag_disabled",
        "enabled": False,
        "query": query,
        "error": "RAG is disabled in scripts/goldfish/config/rag.json",
        "error_type": "rag_disabled",
        "base_url": cfg.base_url,
        "config_path": str(cfg.config_path),
        "safety": _safety(),
    }


def _empty_error(field: str, cfg: RagConfig, *, mode: str) -> Dict[str, Any]:
    payload = {
        "status": "error",
        "mode": mode,
        field: "",
        "error": f"{field} is required",
        "error_type": "empty_query",
        "base_url": cfg.base_url,
        "config_path": str(cfg.config_path),
        "safety": _safety(),
    }
    if mode == "rag_query":
        payload["sources"] = []
        payload["source_count"] = 0
    else:
        payload["results"] = []
        payload["result_count"] = 0
    return payload


def _is_timeout(value: Any) -> bool:
    if isinstance(value, (TimeoutError, socket.timeout)):
        return True
    text = str(value).lower()
    return "timed out" in text or "timeout" in text


def _status_error_type(health: Dict[str, Any], stats: Dict[str, Any]) -> str:
    for payload in (health, stats):
        if payload.get("error_type"):
            return str(payload["error_type"])
    return "service_unavailable"


def _status_error_text(health: Dict[str, Any], stats: Dict[str, Any]) -> str:
    messages = []
    for label, payload in [("health", health), ("stats", stats)]:
        if payload.get("status") != "ok":
            messages.append(f"{label}: {payload.get('error', 'request failed')}")
    return "; ".join(messages) or "RAG status check failed"


def _safety() -> Dict[str, bool]:
    return {
        "local_service_only": True,
        "api_keys_sent": False,
        "cookies_saved": False,
        "private_web_scraping": False,
    }


def _url(cfg: RagConfig, endpoint: str) -> str:
    return cfg.base_url.rstrip("/") + endpoint


def _endpoint(value: Any, default: str) -> str:
    endpoint = str(value or default)
    return endpoint if endpoint.startswith("/") else f"/{endpoint}"


def _int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(min_value, min(max_value, number))
