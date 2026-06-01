"""Search goldfish state and generated Markdown intelligence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .state_store import GoldfishState
from .utils import kb_root, truncate


SEARCH_DIRS = [
    "04_Resources/AI-News",
    "05_Permanent-Notes/AI-Trends",
    "11_Business-Ideas/AI-News-Inspirations",
    "09_Prompts/AI-News",
    "02_Projects/AI-News-Ideas",
]


def search_goldfish(query: str, limit: int = 20, root: Path | None = None) -> Dict[str, Any]:
    root = root or kb_root()
    state = GoldfishState(root)
    results: List[Dict[str, Any]] = []
    results.extend(_search_state(state, query, limit))
    results.extend(_search_files(root, query, limit))
    ranked = sorted(results, key=lambda item: item.get("score", 0), reverse=True)[:limit]
    return {"query": query, "count": len(ranked), "results": ranked}


def _search_state(state: GoldfishState, query: str, limit: int) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for row in state.search_insights(query, limit=limit):
        try:
            payload = json.loads(row.get("payload_json", "{}"))
        except Exception:
            payload = {}
        haystack = " ".join([row.get("title", ""), row.get("target_type", ""), row.get("url", ""), json.dumps(payload, ensure_ascii=False)])
        results.append(
            {
                "type": "insight",
                "title": row.get("title", ""),
                "path": state.path.as_posix(),
                "url": row.get("url", ""),
                "snippet": _snippet(haystack, query),
                "score": 80 + float(row.get("score", 0) or 0),
                "created_at": row.get("created_at", ""),
            }
        )
    for row in state.search_messages(query, limit=limit):
        results.append(
            {
                "type": "message",
                "title": f"{row.get('role', 'message')} message",
                "path": state.path.as_posix(),
                "url": "",
                "snippet": _snippet(row.get("content", ""), query),
                "score": 40,
                "created_at": row.get("created_at", ""),
            }
        )
    return results


def _search_files(root: Path, query: str, limit: int) -> List[Dict[str, Any]]:
    needles = [part.lower() for part in query.split() if part.strip()]
    if not needles:
        needles = [query.lower()]
    results: List[Dict[str, Any]] = []
    for rel_dir in SEARCH_DIRS:
        folder = root / rel_dir
        if not folder.exists():
            continue
        for path in folder.rglob("*.md"):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            lowered = text.lower()
            hits = sum(lowered.count(needle) for needle in needles)
            if hits <= 0:
                continue
            title = _title_from_markdown(path, text)
            results.append(
                {
                    "type": "markdown",
                    "title": title,
                    "path": str(path),
                    "url": "",
                    "snippet": _snippet(text, query),
                    "score": 20 + hits,
                    "created_at": "",
                }
            )
            if len(results) >= limit * 3:
                return results
    return results


def _title_from_markdown(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def _snippet(text: str, query: str) -> str:
    lowered = text.lower()
    first = len(text)
    for part in [part.lower() for part in query.split() if part.strip()] or [query.lower()]:
        index = lowered.find(part)
        if index >= 0:
            first = min(first, index)
    if first == len(text):
        first = 0
    start = max(0, first - 80)
    return truncate(text[start : start + 360], 320)
