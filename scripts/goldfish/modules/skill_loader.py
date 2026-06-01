"""Load lightweight Markdown skills for goldfish."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .utils import agent_dir


def skills_dir() -> Path:
    return agent_dir() / "skills"


def list_skills() -> List[Dict[str, Any]]:
    root = skills_dir()
    skills: List[Dict[str, Any]] = []
    if not root.exists():
        return skills
    for skill_file in sorted(root.glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        title = _first_heading(text) or skill_file.parent.name
        skills.append(
            {
                "name": skill_file.parent.name,
                "title": title,
                "path": str(skill_file),
                "summary": _first_paragraph(text),
            }
        )
    return skills


def load_skill(name: str) -> Dict[str, Any]:
    path = skills_dir() / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill not found: {name}")
    text = path.read_text(encoding="utf-8")
    return {
        "name": name,
        "title": _first_heading(text) or name,
        "path": str(path),
        "content": text,
    }


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _first_paragraph(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if line == "## Purpose":
            for candidate in lines[index + 1 :]:
                if candidate and not candidate.startswith("#"):
                    return candidate
    for line in lines:
        if line and not line.startswith("#"):
            return line
    return ""
