"""First-pass goal-driven agent loop for goldfish.

This module turns a natural-language goal into a small bounded plan, executes
only allow-listed ToolRegistry tools, records observations, and writes a task
workspace. It intentionally avoids arbitrary shell execution and external agent
frameworks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Protocol
from uuid import uuid4

from .config_loader import load_config
from .model_setup import redact_secret_text
from .providers.registry import get_provider, resolve_llm_connection
from .utils import kb_root, now, safe_filename


ALLOWED_TOOLS = {"research_web", "search", "memory_show", "tools", "doctor", "dry_run", "run_daily"}
MAX_RESULT_CHARS = 12000
MAX_TEXT_CHARS = 1800


class RegistryLike(Protocol):
    def execute(self, name: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ...


@dataclass
class PlannedStep:
    step: int
    status: str
    tool: str
    args: Dict[str, Any]
    reason: str


def run_agent_loop(
    goal: str,
    *,
    registry: RegistryLike,
    max_steps: int = 5,
    no_llm: bool = False,
    no_save: bool = False,
    root: Path | None = None,
) -> Dict[str, Any]:
    """Run a bounded goal-driven loop and return a structured result."""

    root = root or kb_root()
    clean_goal = redact_secret_text(goal.strip())
    task = _create_task_workspace(root, clean_goal)
    plan = make_plan(clean_goal, max_steps=max_steps, no_save=no_save)
    observations: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []

    _safe_write(task["path"] / "goal.md", f"# Goal\n\n{clean_goal}\n")
    _safe_write(task["path"] / "plan.md", _plan_markdown(clean_goal, plan))

    for planned in plan[: max(1, min(max_steps, 8))]:
        observation = _execute_step(planned, registry)
        observations.append(observation)
        tool_calls.append(
            {
                "step": planned.step,
                "tool": planned.tool,
                "args": _redact_jsonable(planned.args),
                "success": observation.get("success", False),
                "status": planned.status,
            }
        )
        _append_jsonl(task["path"] / "tool_calls.jsonl", tool_calls[-1])

    summary = _final_answer(clean_goal, plan, observations, no_llm=no_llm)
    files_written = _collect_files_written(task["path"], observations)
    final = {
        "task_id": task["id"],
        "task_path": str(task["path"]),
        "goal": clean_goal,
        "summary": summary["summary"],
        "next_actions": summary["next_actions"],
        "files_written": files_written,
        "observations_count": len(observations),
    }

    _safe_write(task["path"] / "observations.json", json.dumps(observations, ensure_ascii=False, indent=2))
    _safe_write(task["path"] / "final.md", _final_markdown(final, observations))

    return {
        "status": "ok",
        "task_id": task["id"],
        "task_path": str(task["path"]),
        "goal": clean_goal,
        "plan": [_step_dict(step) for step in plan],
        "observations": observations,
        "summary": final["summary"],
        "next_actions": final["next_actions"],
        "files_written": files_written,
        "safety": {
            "arbitrary_shell": False,
            "uses_tool_registry": True,
            "allowed_tools": sorted(ALLOWED_TOOLS),
            "api_keys_saved": False,
        },
    }


def make_plan(goal: str, *, max_steps: int = 5, no_save: bool = False) -> List[PlannedStep]:
    lowered = goal.lower()
    steps: List[PlannedStep] = []

    if _wants_doctor(lowered):
        steps.append(PlannedStep(1, "reading", "doctor", {}, "Goal asks to inspect runtime/config health."))
    if _wants_tools(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "tools", {}, "Goal asks about available capabilities."))
    if _wants_memory(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "memory_show", {}, "Goal asks to inspect memory."))
    if _wants_local_search(lowered):
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "search",
                "search",
                {"query": _strip_intent_words(goal), "limit": 8},
                "Goal asks for local/history/notes search.",
            )
        )
    if _wants_research(lowered):
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "search",
                "research_web",
                {
                    "query": _strip_intent_words(goal),
                    "limit": 5,
                    "fetch_limit": 3,
                    "no_llm": True,
                    "no_save": no_save,
                },
                "Goal asks for public web research or market/trend/opportunity study.",
            )
        )
    if _wants_daily(lowered):
        real_run = _explicit_real_run(lowered)
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "run",
                "run_daily" if real_run else "dry_run",
                {"no_llm": True, "emit_report": False, "write_drafts": real_run},
                "Goal asks for a daily report; defaulting to dry-run unless explicit write/save/run-for-real intent exists.",
            )
        )

    if not steps:
        steps.append(PlannedStep(1, "reading", "tools", {}, "Goal is ambiguous; inspect available tools first."))

    steps.append(PlannedStep(len(steps) + 1, "thinking", "memory_show", {}, "Collect lightweight context before final answer."))
    return steps[: max(1, min(max_steps, 8))]


def _execute_step(step: PlannedStep, registry: RegistryLike) -> Dict[str, Any]:
    if step.tool not in ALLOWED_TOOLS:
        return {
            "step": step.step,
            "status": step.status,
            "tool": step.tool,
            "reason": step.reason,
            "success": False,
            "error": "tool is not allow-listed",
        }
    try:
        result = registry.execute(step.tool, step.args)
        return {
            "step": step.step,
            "status": step.status,
            "tool": step.tool,
            "reason": step.reason,
            "success": result.get("status", "ok") != "error",
            "result": _truncate_json(result),
        }
    except Exception as exc:
        return {
            "step": step.step,
            "status": step.status,
            "tool": step.tool,
            "reason": step.reason,
            "success": False,
            "error": str(exc),
        }


def _final_answer(goal: str, plan: List[PlannedStep], observations: List[Dict[str, Any]], *, no_llm: bool) -> Dict[str, Any]:
    rule_answer = _rule_final(goal, observations)
    if no_llm:
        return rule_answer
    config = load_config()
    connection = resolve_llm_connection(config.settings)
    if not connection.get("api_key"):
        return rule_answer
    prompt = (
        "You are goldfish's local agent loop. Summarize the completed tool observations. "
        "Do not invent sources, files, or API keys. Return concise JSON with keys summary and next_actions."
    )
    payload = {
        "goal": goal,
        "plan": [_step_dict(step) for step in plan],
        "observations": _truncate_json(observations, max_chars=6000),
    }
    try:
        text = get_provider(config.settings).generate_text(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
        parsed = json.loads(_extract_json(text))
        return {
            "summary": str(parsed.get("summary") or rule_answer["summary"]),
            "next_actions": [str(item) for item in parsed.get("next_actions", rule_answer["next_actions"])][:5],
        }
    except Exception:
        return rule_answer


def _rule_final(goal: str, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    successful = [obs for obs in observations if obs.get("success")]
    failed = [obs for obs in observations if not obs.get("success")]
    tools = ", ".join(obs.get("tool", "") for obs in observations) or "none"
    summary = f"Agent loop handled the goal with {len(observations)} step(s). Tools used: {tools}."
    if successful:
        summary += f" Successful steps: {len(successful)}."
    if failed:
        summary += f" Failed/degraded steps: {len(failed)}."
    next_actions = [
        "Review the task workspace observations.",
        "Open any generated Markdown reports or drafts before treating them as final.",
        "Run a more specific /agent goal if you want a narrower follow-up.",
    ]
    if _wants_research(goal.lower()):
        next_actions.insert(0, "Verify high-value web sources before converting them into permanent notes or business ideas.")
    return {"summary": summary, "next_actions": next_actions[:5]}


def _create_task_workspace(root: Path, goal: str) -> Dict[str, Any]:
    stamp = now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:6]
    slug = safe_filename(goal)[:40] or "goal"
    task_id = f"task-{stamp}-{suffix}"
    path = root / "scripts" / "goldfish" / "output_cache" / "tasks" / f"{task_id}-{slug}"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        fallback = root / "scripts" / "goldfish" / "output_cache" / "tasks" / task_id
        fallback.mkdir(parents=True, exist_ok=True)
        path = fallback
    return {"id": task_id, "path": path}


def _safe_write(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(redact_secret_text(text), encoding="utf-8")
    except Exception:
        return


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_redact_jsonable(payload), ensure_ascii=False) + "\n")
    except Exception:
        return


def _plan_markdown(goal: str, plan: List[PlannedStep]) -> str:
    lines = [f"# Plan\n\nGoal: {goal}\n"]
    for step in plan:
        lines.append(f"{step.step}. `{step.tool}` ({step.status}) - {step.reason}")
    return "\n".join(lines) + "\n"


def _final_markdown(final: Dict[str, Any], observations: List[Dict[str, Any]]) -> str:
    lines = [
        "# Agent Loop Result",
        "",
        f"- task_id: `{final['task_id']}`",
        f"- goal: {final['goal']}",
        "",
        "## Summary",
        "",
        final["summary"],
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in final["next_actions"])
    lines.extend(["", "## Observations", ""])
    for obs in observations:
        lines.append(f"- Step {obs.get('step')}: `{obs.get('tool')}` status={obs.get('status')} success={obs.get('success')}")
    return "\n".join(lines) + "\n"


def _collect_files_written(task_path: Path, observations: List[Dict[str, Any]]) -> List[str]:
    files = [str(task_path / name) for name in ("goal.md", "plan.md", "observations.json", "tool_calls.jsonl", "final.md")]
    for obs in observations:
        result = obs.get("result", {})
        if isinstance(result, dict):
            files.extend(_extract_written_paths(result))
    return sorted(set(files))


def _extract_written_paths(value: Any) -> List[str]:
    paths: List[str] = []
    if isinstance(value, dict):
        for key in ("report_path", "weekly_path", "dashboard_path", "knowledge_report_path", "feedback_report_path"):
            nested = value.get(key)
            if isinstance(nested, str) and nested:
                paths.append(nested)
        draft_paths = value.get("draft_paths")
        if isinstance(draft_paths, list):
            paths.extend(str(path) for path in draft_paths if path)
        for key, nested in value.items():
            if key in {"path", "task_path"}:
                continue
            paths.extend(_extract_written_paths(nested))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_extract_written_paths(item))
    return paths


def _step_dict(step: PlannedStep) -> Dict[str, Any]:
    return {"step": step.step, "status": step.status, "tool": step.tool, "args": step.args, "reason": step.reason}


def _truncate_json(value: Any, max_chars: int = MAX_RESULT_CHARS) -> Any:
    return json.loads(_truncate_text(json.dumps(_redact_jsonable(value), ensure_ascii=False, default=str), max_chars=max_chars))


def _truncate_text(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    safe = redact_secret_text(text)
    if len(safe) <= max_chars:
        return safe
    return safe[:max_chars] + f"\n...[truncated {len(safe) - max_chars} chars]"


def _redact_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_jsonable(nested) for key, nested in value.items() if "api_key" not in str(key).lower()}
    if isinstance(value, list):
        return [_redact_jsonable(item) for item in value]
    if isinstance(value, str):
        return _truncate_text(value)
    return value


def _extract_json(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.S)
    return match.group(0) if match else text


def _wants_research(lowered: str) -> bool:
    return any(
        word in lowered
        for word in [
            "research",
            "web",
            "investigate",
            "study",
            "market",
            "opportunity",
            "opportunities",
            "trend",
            "mcp",
            "rag",
            "ai coding",
            "agent",
            "商业机会",
            "研究",
            "趋势",
            "市场",
        ]
    )


def _wants_local_search(lowered: str) -> bool:
    if any(word in lowered for word in ["history", "local", "previous", "saved", "notes", "历史", "本地", "笔记"]):
        return True
    return bool(re.search(r"\bsearch\b", lowered))


def _wants_daily(lowered: str) -> bool:
    return any(word in lowered for word in ["daily report", "briefing", "日报", "run daily", "today report"])


def _wants_memory(lowered: str) -> bool:
    return "memory" in lowered or "记忆" in lowered


def _wants_tools(lowered: str) -> bool:
    return "tools" in lowered or "capabilities" in lowered or "能力" in lowered


def _wants_doctor(lowered: str) -> bool:
    return "doctor" in lowered or "diagnose" in lowered or "诊断" in lowered


def _explicit_real_run(lowered: str) -> bool:
    return any(phrase in lowered for phrase in ["write", "save", "run for real", "for real", "正式", "写入", "保存"])


def _strip_intent_words(goal: str) -> str:
    cleaned = re.sub(
        r"\b(research|web|investigate|study|market|opportunity|opportunities|trend|search|history|local|previous|saved|notes|please|help me)\b",
        " ",
        goal,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or goal.strip()
