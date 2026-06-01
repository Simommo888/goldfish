"""Update Obsidian Home dashboard without rewriting unrelated sections."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .utils import kb_root


START = "<!-- AI_NEWS_DAILY_START -->"
END = "<!-- AI_NEWS_DAILY_END -->"


def _daily_link(date_text: str) -> str:
    return f"- [[04_Resources/AI-News/Daily/AI情报日报-{date_text}|AI情报日报-{date_text}]]"


def _extract_existing_links(block: str) -> List[str]:
    return [line.strip() for line in block.splitlines() if "AI情报日报-" in line and line.strip().startswith("-")]


def update_home_dashboard(date_text: str, root: Path | None = None, max_links: int = 7) -> Path | None:
    root = root or kb_root()
    home = root / "01_Dashboard" / "Home.md"
    if not home.exists():
        return None
    content = home.read_text(encoding="utf-8", errors="replace")
    new_link = _daily_link(date_text)

    if START in content and END in content:
        pattern = re.compile(re.escape(START) + r"(.*?)" + re.escape(END), flags=re.S)
        match = pattern.search(content)
        existing = _extract_existing_links(match.group(1) if match else "")
        links = [new_link] + [line for line in existing if line != new_link]
        links = links[:max_links]
        replacement = START + "\n" + "\n".join(links) + "\n" + END
        content = pattern.sub(replacement, content)
    elif "## 最近沉淀" in content:
        marker_block = "## 最近沉淀\n\n" + START + "\n" + new_link + "\n" + END + "\n"
        content = content.replace("## 最近沉淀", marker_block, 1)
    else:
        section = "\n\n## AI 情报日报\n\n" + START + "\n" + new_link + "\n" + END + "\n"
        content = content.rstrip() + section

    home.write_text(content, encoding="utf-8")
    return home
