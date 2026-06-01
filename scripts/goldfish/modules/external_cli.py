"""Allow-listed external CLI tools for goldfish.

External commands are powerful, so goldfish runs only tools declared in
config/external_tools.json. Commands default to shell=False, keep cwd inside
the project, redact secrets from output, and truncate long results.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .model_setup import redact_secret_text
from .utils import agent_dir, kb_root


@dataclass(frozen=True)
class ExternalTool:
    name: str
    description: str
    runner: str
    command: str | List[str]
    defaults: Dict[str, Any]
    required_args: List[str]
    mutating: bool
    allowed_cwd: List[str]
    timeout_seconds: int
    max_output_chars: int


def external_tools_config_path() -> Path:
    return agent_dir() / "config" / "external_tools.json"


def load_external_tools() -> Dict[str, Any]:
    path = external_tools_config_path()
    if not path.exists():
        return {
            "path": str(path),
            "default_timeout_seconds": 20,
            "default_max_output_chars": 12000,
            "tools": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("path", str(path))
    payload.setdefault("tools", [])
    payload.setdefault("default_timeout_seconds", 20)
    payload.setdefault("default_max_output_chars", 12000)
    return payload


def list_external_tools(include_disabled: bool = False) -> List[Dict[str, Any]]:
    config = load_external_tools()
    tools: List[Dict[str, Any]] = []
    for raw in config.get("tools", []):
        if not raw.get("enabled", False) and not include_disabled:
            continue
        tools.append(
            {
                "name": raw.get("name", ""),
                "enabled": bool(raw.get("enabled", False)),
                "description": raw.get("description", ""),
                "runner": raw.get("runner", "direct"),
                "mutating": bool(raw.get("mutating", False)),
                "required_args": list(raw.get("required_args", [])),
            }
        )
    return tools


def run_external_tool(
    name: str,
    args: Dict[str, Any] | None = None,
    *,
    cwd: str | None = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    tool = _get_tool(name)
    values = dict(tool.defaults)
    values.update({key: value for key, value in (args or {}).items() if value is not None})

    missing = [key for key in tool.required_args if not str(values.get(key, "")).strip()]
    if missing:
        return {"status": "error", "error": f"missing required args: {', '.join(missing)}", "tool_name": name}

    workdir = _resolve_cwd(cwd or values.pop("cwd", None) or ".", tool.allowed_cwd)
    values = _normalize_path_args(values, workdir)
    command = _render_command(tool, values)
    if dry_run:
        return {
            "status": "ok",
            "dry_run": True,
            "tool_name": name,
            "runner": tool.runner,
            "cwd": str(workdir),
            "command": _redact_command(command),
            "mutating": tool.mutating,
        }

    try:
        completed = subprocess.run(
            command,
            cwd=str(workdir),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=tool.timeout_seconds,
            shell=False,
        )
        stdout = _truncate(redact_secret_text(completed.stdout or ""), tool.max_output_chars)
        stderr = _truncate(redact_secret_text(completed.stderr or ""), tool.max_output_chars)
        return {
            "status": "ok" if completed.returncode == 0 else "error",
            "tool_name": name,
            "runner": tool.runner,
            "cwd": str(workdir),
            "command": _redact_command(command),
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "mutating": tool.mutating,
        }
    except FileNotFoundError as exc:
        return {
            "status": "error",
            "tool_name": name,
            "cwd": str(workdir),
            "command": _redact_command(command),
            "error": f"command not found: {exc.filename}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "tool_name": name,
            "cwd": str(workdir),
            "command": _redact_command(command),
            "error": f"command timed out after {tool.timeout_seconds}s",
            "stdout": _truncate(redact_secret_text(exc.stdout or ""), tool.max_output_chars),
            "stderr": _truncate(redact_secret_text(exc.stderr or ""), tool.max_output_chars),
        }
    except Exception as exc:
        return {
            "status": "error",
            "tool_name": name,
            "cwd": str(workdir),
            "command": _redact_command(command),
            "error": str(exc),
        }


def _get_tool(name: str) -> ExternalTool:
    config = load_external_tools()
    defaults_timeout = int(config.get("default_timeout_seconds", 20) or 20)
    defaults_output = int(config.get("default_max_output_chars", 12000) or 12000)
    for raw in config.get("tools", []):
        if raw.get("name") != name:
            continue
        if not raw.get("enabled", False):
            raise ValueError(f"external tool is disabled: {name}")
        return ExternalTool(
            name=str(raw.get("name")),
            description=str(raw.get("description", "")),
            runner=str(raw.get("runner", "direct") or "direct"),
            command=raw.get("command", []),
            defaults=dict(raw.get("defaults", {})),
            required_args=list(raw.get("required_args", [])),
            mutating=bool(raw.get("mutating", False)),
            allowed_cwd=list(raw.get("allowed_cwd", ["."])),
            timeout_seconds=int(raw.get("timeout_seconds", defaults_timeout) or defaults_timeout),
            max_output_chars=int(raw.get("max_output_chars", defaults_output) or defaults_output),
        )
    raise KeyError(f"unknown external tool: {name}")


def _render_command(tool: ExternalTool, values: Dict[str, Any]) -> List[str]:
    if tool.runner == "direct":
        if not isinstance(tool.command, list):
            raise ValueError(f"direct runner requires command array for {tool.name}")
        return [_render_part(str(part), values) for part in tool.command]
    if tool.runner == "bash":
        if isinstance(tool.command, list):
            script = " ".join(shlex.quote(_render_part(str(part), values)) for part in tool.command)
        else:
            script = _render_shell_script(str(tool.command), values)
        return ["bash", "-lc", script]
    if tool.runner == "powershell":
        script = _render_shell_script(str(tool.command), values)
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    if tool.runner == "cmd":
        script = _render_shell_script(str(tool.command), values)
        return ["cmd", "/d", "/c", script]
    raise ValueError(f"unsupported external runner: {tool.runner}")


def _render_part(template: str, values: Dict[str, Any]) -> str:
    return template.format(**{key: str(value) for key, value in values.items()})


def _render_shell_script(template: str, values: Dict[str, Any]) -> str:
    quoted = {key: shlex.quote(str(value)) for key, value in values.items()}
    return template.format(**quoted)


def _resolve_cwd(cwd: str, allowed: List[str]) -> Path:
    root = kb_root().resolve()
    candidate = (root / cwd).resolve() if not Path(cwd).is_absolute() else Path(cwd).resolve()
    allowed_roots = [((root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()) for path in allowed or ["."]]
    if not any(candidate == base or base in candidate.parents for base in allowed_roots):
        raise ValueError(f"cwd is outside allowed paths: {candidate}")
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _normalize_path_args(values: Dict[str, Any], workdir: Path) -> Dict[str, Any]:
    normalized = dict(values)
    for key, value in values.items():
        if key not in {"path", "file", "dir", "directory", "target"}:
            continue
        text = str(value).strip()
        if not text or _looks_like_glob_or_option(text):
            continue
        candidate = (workdir / text).resolve() if not Path(text).is_absolute() else Path(text).resolve()
        root = kb_root().resolve()
        if not (candidate == root or root in candidate.parents):
            raise ValueError(f"{key} is outside project root: {candidate}")
        try:
            normalized[key] = str(candidate.relative_to(workdir.resolve()))
        except Exception:
            normalized[key] = str(candidate)
    return normalized


def _looks_like_glob_or_option(value: str) -> bool:
    return value.startswith("-") or any(char in value for char in "*?[]{}")


def _redact_command(command: List[str]) -> List[str]:
    return [redact_secret_text(part) for part in command]


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 40)] + "\n...[truncated by goldfish]..."
