"""Storage helpers for Markdown reports and JSON cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .utils import date_range_last_days, kb_root, safe_filename


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any) -> Path:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_markdown(path: Path, markdown: str) -> Path:
    ensure_parent(path)
    path.write_text(markdown, encoding="utf-8")
    return path


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def daily_report_path(date_text: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "04_Resources" / "AI-News" / "Daily" / f"AI情报日报-{date_text}.md"


def people_report_path(date_text: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "04_Resources" / "AI-News" / "People-Watch" / f"AI大佬动态-{date_text}.md"


def weekly_report_path(week_text: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "04_Resources" / "AI-News" / "Weekly" / f"AI趋势周报-{week_text}.md"


def raw_cache_path(date_text: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "04_Resources" / "AI-News" / "Raw" / f"{date_text}.json"


def read_recent_daily_reports(date_text: str, days: int = 7, root: Path | None = None) -> List[Dict[str, str]]:
    root = root or kb_root()
    reports = []
    for day in date_range_last_days(date_text, days):
        path = daily_report_path(day, root)
        if path.exists():
            reports.append({"date": day, "path": str(path), "content": read_text_if_exists(path)})
    return reports


def make_safe_filename(title: str, suffix: str = ".md") -> str:
    return f"{safe_filename(title)}{suffix}"
