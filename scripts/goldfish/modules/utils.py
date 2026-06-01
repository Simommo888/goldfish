"""Shared utilities for goldfish.

Safety boundary: this agent only reads public pages/RSS feeds, does not log in,
does not store cookies, does not bypass anti-scraping controls, and marks
unavailable sources as manual-review items instead of inventing facts.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.request import Request, urlopen

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None  # type: ignore


USER_AGENT = (
    "DailyAINewsAgent/1.0 "
    "(public RSS/manual review only; no login; no anti-scraping bypass)"
)


def agent_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def kb_root() -> Path:
    return Path(__file__).resolve().parents[3]


def now(timezone_name: str = "Asia/Shanghai") -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except Exception:
            pass
    return datetime.now(timezone.utc)


def today_string(timezone_name: str = "Asia/Shanghai") -> str:
    return now(timezone_name).strftime("%Y-%m-%d")


def week_string(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def is_weekend(date_text: str) -> bool:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    return dt.weekday() >= 5


def safe_filename(value: str, max_length: int = 120) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\r\n\t]+', "-", value).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "untitled")[:max_length]


def slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    return value.strip("-") or "item"


def strip_html(value: str) -> str:
    value = re.sub(r"<(script|style).*?</\1>", "", value or "", flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def truncate(value: str, max_length: int = 500) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."


def stable_hash(value: str) -> str:
    return hashlib.sha256((value or "").strip().lower().encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    value = strip_html(value).lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value).strip()


def simple_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def contains_any(text: str, keywords: Iterable[str]) -> List[str]:
    lowered = (text or "").lower()
    hits = []
    for keyword in keywords:
        if keyword and keyword.lower() in lowered:
            hits.append(keyword)
    return hits


def fetch_url(url: str, timeout: int = 10) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def get_env(name: str, default: str = "") -> str:
    """Read process env, then Windows user env written by `goldfish setup`.

    New Windows shells usually inherit HKCU\\Environment, but already-open
    terminals often do not. goldfish setup writes API keys there, so runtime
    code must read it directly instead of trusting only the current process.
    """

    value = os.getenv(name)
    if value:
        return value
    if os.getenv("GOLDFISH_IGNORE_USER_ENV"):
        return default
    if sys.platform.startswith("win"):
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                stored, _ = winreg.QueryValueEx(key, name)
                return str(stored or default)
        except Exception:
            return default
    return default


def log(message: str, verbose: bool = False) -> None:
    if verbose:
        print(f"[goldfish] {message}")


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def markdown_link(title: str, url: str) -> str:
    if not url:
        return title
    return f"[{title}]({url})"


def date_range_last_days(date_text: str, days: int) -> List[str]:
    end = datetime.strptime(date_text, "%Y-%m-%d")
    return [(end - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]


def make_manual_item(
    title: str,
    url: str,
    source_name: str,
    source_category: str,
    notes: str = "待人工查看。",
) -> Dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "source_name": source_name,
        "source_category": source_category,
        "published": "",
        "summary": notes,
        "raw_content": notes,
        "fetched_at": now().isoformat(),
        "needs_manual_review": True,
        "manual_review_reason": notes,
    }


def item_text(item: Dict[str, Any]) -> str:
    parts = [
        str(item.get("title", "")),
        str(item.get("summary", "")),
        str(item.get("raw_content", "")),
        str(item.get("source_name", "")),
    ]
    return " ".join(parts)
