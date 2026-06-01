from __future__ import annotations

import shutil
import sys
from typing import Any, Iterable

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


COLOR_BACKGROUND = "#02070a"
COLOR_ORANGE = "#ff941f"
COLOR_ORANGE_SOFT = "#ffb35a"
COLOR_CYAN = "#8eeeff"
COLOR_GREEN = "#73d86b"
COLOR_YELLOW = "#f6c65b"
COLOR_RED = "#ff6b5f"
COLOR_BODY = "#f1e5d0"
COLOR_MUTED = "#8a8f92"
COLOR_LINE = "#5d6264"


def print_doctor_report(report: dict[str, Any], *, console: Console | None = None) -> None:
    _prefer_utf8_terminal()
    width = max(100, min(140, shutil.get_terminal_size((120, 40)).columns))
    console = console or Console(color_system="truecolor", legacy_windows=False, width=width)
    console.print(build_doctor_report(report))


def build_doctor_report(report: dict[str, Any]) -> Group:
    checks = list(_collect_checks(report))
    issues = [check for check in checks if check[0] in {"fail", "warn"}]
    body = Group(
        _header(report, checks),
        Text(""),
        _section("Python Environment", _runtime_rows(report)),
        Text(""),
        _section("Required Packages", _package_rows(report)),
        Text(""),
        _section("Configuration", _config_rows(report)),
        Text(""),
        _section("Workspace", _workspace_rows(report)),
        Text(""),
        _section("Knowledge Base", _knowledge_rows(report)),
        Text(""),
        _summary_panel(issues),
    )
    return Panel(
        body,
        title=f"[bold {COLOR_ORANGE}]><(((o> GOLDFISH DOCTOR[/]",
        subtitle=f"[{COLOR_GREEN}]gf doctor[/] [{COLOR_MUTED}]static checks[/]",
        border_style=COLOR_LINE,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _header(report: dict[str, Any], checks: list[tuple[str, str, str]]) -> Panel:
    counts = {
        "ok": sum(1 for level, _, _ in checks if level == "ok"),
        "warn": sum(1 for level, _, _ in checks if level == "warn"),
        "fail": sum(1 for level, _, _ in checks if level == "fail"),
    }
    grid = Table.grid(padding=(0, 4))
    grid.add_column("brand", ratio=1)
    grid.add_column("status", ratio=1)

    brand = Text()
    brand.append("goldfish", style=f"bold {COLOR_ORANGE}")
    brand.append(" doctor\n", style=f"bold {COLOR_CYAN}")
    brand.append("small agent, sharp memory\n", style=COLOR_CYAN)
    brand.append(str(report.get("kb_root") or "workspace unknown"), style=COLOR_MUTED)

    status = Table.grid(padding=(0, 2))
    status.add_column("key", style=COLOR_MUTED, no_wrap=True)
    status.add_column("value", no_wrap=True)
    status.add_row("ok", f"[{COLOR_GREEN}]{counts['ok']}[/]")
    status.add_row("warnings", f"[{COLOR_YELLOW}]{counts['warn']}[/]")
    status.add_row("failures", f"[{COLOR_RED}]{counts['fail']}[/]")
    status.add_row("provider", f"[{COLOR_BODY}]{report.get('provider', 'unknown')}[/]")
    status.add_row("model", f"[{COLOR_BODY}]{report.get('model', 'unknown')}[/]")

    grid.add_row(brand, status)
    return Panel(grid, border_style=COLOR_LINE, box=box.ROUNDED, padding=(1, 2))


def _section(title: str, rows: Iterable[tuple[str, str, str]]) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column("state", no_wrap=True)
    table.add_column("name", style=COLOR_BODY)
    table.add_column("detail", style=COLOR_MUTED)
    for level, name, detail in rows:
        table.add_row(_mark(level), name, detail)
    return Panel(
        table,
        title=f"[bold {COLOR_ORANGE}]{title.upper()}[/]",
        border_style=COLOR_LINE,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _runtime_rows(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    python = report.get("python") or {}
    version = str(python.get("version") or "unknown")
    py_level = "ok" if _python_ok(version) else "fail"
    package = report.get("goldfish_package") or {}
    skills = report.get("skills") or {}
    return [
        (py_level, f"Python {version}", str(python.get("executable") or "")),
        (_bool_level(package.get("installed"), warn=True), "goldfish package", _package_detail(package)),
        ("ok", "skills", f"{skills.get('count', 0)} loaded from {skills.get('skills_dir', '')}"),
    ]


def _package_rows(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    packages = report.get("required_packages") or {}
    if not packages:
        return [
            (_bool_level(report.get("openai_package")), "openai", "required for LLM providers"),
        ]
    return [
        (_bool_level(status.get("installed")), name, _package_detail(status))
        for name, status in sorted(packages.items())
    ]


def _config_rows(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = [
        (_bool_level(report.get("config_ok")), "config bundle", "sources, keywords, and settings loaded"),
    ]
    for name, ok in sorted((report.get("config_files") or {}).items()):
        rows.append((_bool_level(ok), name, "valid JSON" if ok else "missing or invalid"))

    api_key = bool(report.get("has_model_api_key"))
    rows.extend(
        [
            ("ok", "provider", str(report.get("provider") or "unknown")),
            ("ok", "model", str(report.get("model") or "unknown")),
            ("ok", "base URL", str(report.get("base_url") or "default")),
            ("ok" if api_key else "warn", "model API key", "present" if api_key else "missing; LLM replies will fail"),
            ("ok", "draft write mode", str(report.get("draft_write_mode") or "suggest")),
        ]
    )
    rows.append(_connectivity_row(report.get("deepseek_api") or {}))
    return rows


def _workspace_rows(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    rows = [
        ("ok", "knowledge root", str(report.get("kb_root") or "")),
        ("ok", "agent directory", str(report.get("agent_dir") or "")),
        ("ok", "state database", str(report.get("state_db") or "")),
    ]
    for name, ok in sorted((report.get("writable") or {}).items()):
        rows.append((_bool_level(ok), name, "writable" if ok else "not writable"))
    return rows


def _knowledge_rows(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for path, ok in sorted((report.get("obsidian_dirs") or {}).items()):
        rows.append(("ok" if ok else "warn", path, "exists" if ok else "missing"))

    actions = report.get("github_actions") or {}
    if actions.get("exists"):
        rows.append(("ok", "GitHub Actions workflow", "goldfish.yml found"))
        for key in ("uses_deepseek_secret", "uses_goldfish_cli", "commits_reports", "commits_drafts"):
            rows.append((_bool_level(actions.get(key), warn=True), key.replace("_", " "), "configured" if actions.get(key) else "not configured"))
    else:
        rows.append(("warn", "GitHub Actions workflow", "missing .github/workflows/goldfish.yml"))

    source_health = report.get("source_health") or {}
    failing = source_health.get("failing_sources") or []
    valuable = source_health.get("valuable_sources") or []
    rows.append(("warn" if failing else "ok", "source failures", f"{len(failing)} recent failing source groups"))
    rows.append(("ok", "valuable sources", f"{len(valuable)} tracked source groups"))

    last_run = report.get("last_run")
    if last_run:
        rows.append(("ok", "last run", str(last_run.get("created_at") or last_run.get("date") or "recorded")))
    else:
        rows.append(("warn", "last run", "no run history found"))
    return rows


def _summary_panel(issues: list[tuple[str, str, str]]) -> Panel:
    if not issues:
        text = Text("All required checks passed.", style=COLOR_GREEN)
    else:
        text = Text()
        text.append(f"{len(issues)} item(s) need attention\n", style=f"bold {COLOR_YELLOW}")
        for index, (level, name, detail) in enumerate(issues, start=1):
            text.append(f"{index}. ", style=COLOR_MUTED)
            text.append(name, style=COLOR_RED if level == "fail" else COLOR_YELLOW)
            if detail:
                text.append(f" - {detail}", style=COLOR_MUTED)
            if index < len(issues):
                text.append("\n")
    return Panel(
        text,
        title=f"[bold {COLOR_ORANGE}]SUMMARY[/]",
        border_style=COLOR_LINE,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _collect_checks(report: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    yield from _runtime_rows(report)
    yield from _package_rows(report)
    yield from _config_rows(report)
    yield from _workspace_rows(report)
    yield from _knowledge_rows(report)


def _mark(level: str) -> str:
    if level == "ok":
        return f"[{COLOR_GREEN}]✓ ok[/]"
    if level == "warn":
        return f"[{COLOR_YELLOW}]! warn[/]"
    if level == "fail":
        return f"[{COLOR_RED}]x fail[/]"
    return f"[{COLOR_CYAN}]· info[/]"


def _bool_level(value: Any, *, warn: bool = False) -> str:
    if bool(value):
        return "ok"
    return "warn" if warn else "fail"


def _connectivity_row(status: dict[str, Any]) -> tuple[str, str, str]:
    if not status.get("checked"):
        return ("warn", "DeepSeek connectivity", str(status.get("reason") or "not checked"))
    if status.get("ok"):
        return ("ok", "DeepSeek connectivity", str(status.get("response_preview") or "reachable"))
    return ("fail", "DeepSeek connectivity", str(status.get("error") or status.get("reason") or "request failed"))


def _package_detail(package: dict[str, Any]) -> str:
    if package.get("installed"):
        return f"version {package.get('version', 'unknown')}"
    return str(package.get("error") or "not installed")


def _python_ok(version: str) -> bool:
    try:
        major, minor, *_ = [int(part) for part in version.split(".")]
    except Exception:
        return False
    return (major, minor) >= (3, 10)


def _prefer_utf8_terminal() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
