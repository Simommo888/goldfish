"""Write goldfish outputs into the Obsidian vault."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from . import storage
from .utils import week_string


def write_daily_outputs(
    date_text: str,
    daily_markdown: str,
    people_markdown: str,
    raw_payload: Dict[str, Any],
    root: Path | None = None,
) -> Dict[str, Path]:
    root = root or storage.kb_root()
    raw_path = storage.save_json(storage.raw_cache_path(date_text, root), raw_payload)
    daily_path = storage.save_markdown(storage.daily_report_path(date_text, root), daily_markdown)
    people_path = storage.save_markdown(storage.people_report_path(date_text, root), people_markdown)
    return {"raw": raw_path, "daily": daily_path, "people": people_path}


def write_weekly_output(date_text: str, weekly_markdown: str, root: Path | None = None) -> Path:
    root = root or storage.kb_root()
    return storage.save_markdown(storage.weekly_report_path(week_string(date_text), root), weekly_markdown)
