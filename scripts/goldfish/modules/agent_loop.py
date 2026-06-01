"""Plan/execute agent loop for goldfish.

This module turns a natural-language goal into a bounded plan, executes one
allow-listed ToolRegistry tool at a time, records observations, and revises the
plan when a fallback is useful. The shape is intentionally close to the
"plan -> execute -> observe -> revise -> final" loop used by coding agents,
while staying small enough for a local knowledge-base assistant.
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


ALLOWED_TOOLS = {"research_web", "search", "memory_show", "tools", "doctor", "dry_run", "run_daily", "external_cli"}
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


@dataclass
class PlanRevision:
    revision: int
    reason: str
    steps: List[PlannedStep]
    created_at: str


def run_agent_loop(
    goal: str,
    *,
    registry: RegistryLike,
    max_steps: int = 5,
    no_llm: bool = False,
    no_save: bool = False,
    root: Path | None = None,
) -> Dict[str, Any]:
    """Run a bounded plan/execute loop and return a structured result."""

    root = root or kb_root()
    clean_goal = redact_secret_text(goal.strip())
    task = _create_task_workspace(root, clean_goal)
    step_limit = max(1, min(max_steps, 8))
    plan = make_plan(clean_goal, max_steps=step_limit, no_save=no_save)
    plan_revisions = [_plan_revision_payload(0, "initial plan", plan)]
    observations: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []
    stop_reason = "plan_complete"

    _safe_write(task["path"] / "goal.md", f"# Goal\n\n{clean_goal}\n")
    _safe_write(task["path"] / "plan.md", _plan_markdown(clean_goal, plan))
    _append_jsonl(task["path"] / "plan_revisions.jsonl", plan_revisions[0])
    _write_execution_state(task["path"], clean_goal, plan, observations, plan_revisions, "planning", "")

    cursor = 0
    while cursor < len(plan) and len(observations) < step_limit:
        planned = plan[cursor]
        _write_execution_state(task["path"], clean_goal, plan, observations, plan_revisions, "executing", f"step-{planned.step}")
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
        _safe_write(task["path"] / "observations.json", json.dumps(observations, ensure_ascii=False, indent=2))

        decision = _decide_next(clean_goal, plan, observations, step_limit=step_limit, no_save=no_save)
        if decision["action"] == "revise":
            plan = decision["plan"]
            revision = _plan_revision_payload(len(plan_revisions), decision["reason"], plan)
            plan_revisions.append(revision)
            _append_jsonl(task["path"] / "plan_revisions.jsonl", revision)
            _safe_write(task["path"] / "plan.md", _plan_markdown(clean_goal, plan, plan_revisions))
        elif decision["action"] == "stop":
            stop_reason = decision["reason"]
            break

        cursor += 1

    if len(observations) >= step_limit and cursor < len(plan):
        stop_reason = "max_steps_reached"

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
        "execution": {
            "mode": "plan_execute",
            "plan_revisions": len(plan_revisions),
            "steps_executed": len(observations),
            "stop_reason": stop_reason,
        },
    }

    _safe_write(task["path"] / "observations.json", json.dumps(observations, ensure_ascii=False, indent=2))
    _write_execution_state(task["path"], clean_goal, plan, observations, plan_revisions, "final", stop_reason)
    _safe_write(task["path"] / "final.md", _final_markdown(final, observations))

    return {
        "status": "ok",
        "task_id": task["id"],
        "task_path": str(task["path"]),
        "goal": clean_goal,
        "plan": [_step_dict(step) for step in plan],
        "observations": observations,
        "plan_revisions": plan_revisions,
        "execution": final["execution"],
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
    if _wants_external_cli(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "external_cli", {"action": "list"}, "Goal asks about external CLI tools."))
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
                    "search_provider": _preferred_search_provider(lowered),
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


def _decide_next(
    goal: str,
    plan: List[PlannedStep],
    observations: List[Dict[str, Any]],
    *,
    step_limit: int,
    no_save: bool,
) -> Dict[str, Any]:
    """Decide whether to continue, revise, or stop after an observation."""

    if not observations:
        return {"action": "continue", "reason": "no observations yet", "plan": plan}

    if len(observations) >= step_limit:
        return {"action": "stop", "reason": "max_steps_reached", "plan": plan}

    last = observations[-1]
    revised = _revise_plan(goal, plan, observations, step_limit=step_limit, no_save=no_save)
    if revised is not None:
        return {"action": "revise", "reason": revised["reason"], "plan": revised["plan"]}

    if not last.get("success") and _no_more_unexecuted_steps(plan, observations):
        return {"action": "stop", "reason": "last_step_failed_no_fallback", "plan": plan}

    if _no_more_unexecuted_steps(plan, observations):
        return {"action": "stop", "reason": "plan_complete", "plan": plan}

    return {"action": "continue", "reason": "next_planned_step", "plan": plan}


def _revise_plan(
    goal: str,
    plan: List[PlannedStep],
    observations: List[Dict[str, Any]],
    *,
    step_limit: int,
    no_save: bool,
) -> Dict[str, Any] | None:
    """Add bounded fallback steps based on the latest observation."""

    if len(plan) >= step_limit:
        return None

    lowered = goal.lower()
    last = observations[-1]
    used_tools = {str(obs.get("tool")) for obs in observations}
    planned_tools = {step.tool for step in plan}

    if last.get("tool") == "research_web" and not last.get("success") and "search" not in used_tools | planned_tools:
        new_plan = _insert_next_step(
            plan,
            observations,
            status="search",
            tool="search",
            args={"query": _strip_intent_words(goal), "limit": 8},
            reason="Web research failed or degraded; fall back to local history search.",
        )
        return {"reason": "research_web_failed_add_local_search", "plan": new_plan}

    if last.get("tool") in {"dry_run", "run_daily"} and not last.get("success") and "doctor" not in used_tools | planned_tools:
        new_plan = _insert_next_step(
            plan,
            observations,
            status="reading",
            tool="doctor",
            args={},
            reason="Report run failed; inspect runtime health before final answer.",
        )
        return {"reason": "report_run_failed_add_doctor", "plan": new_plan}

    if last.get("tool") == "external_cli" and last.get("success") and _wants_project_search(lowered):
        already_runs_external = any(
            obs.get("tool") == "external_cli" and isinstance(obs.get("result"), dict) and obs.get("result", {}).get("action") == "run"
            for obs in observations
        )
        planned_external_run = any(step.tool == "external_cli" and step.args.get("action") == "run" for step in plan)
        if not already_runs_external and not planned_external_run:
            new_plan = _insert_next_step(
                plan,
                observations,
                status="search",
                tool="external_cli",
                args={
                    "action": "run",
                    "name": "rg_search",
                    "args": {"query": _strip_intent_words(goal), "path": "scripts/goldfish"},
                },
                reason="Goal asks for project/file search; use allow-listed ripgrep wrapper.",
            )
            return {"reason": "external_cli_listed_add_rg_search", "plan": new_plan}

    if not any(obs.get("success") for obs in observations) and "doctor" not in used_tools | planned_tools:
        new_plan = _insert_next_step(
            plan,
            observations,
            status="reading",
            tool="doctor",
            args={},
            reason="No successful observations yet; run doctor as a safe diagnostic fallback.",
        )
        return {"reason": "no_successful_observations_add_doctor", "plan": new_plan}

    return None


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


def _wants_external_cli(text: str) -> bool:
    return any(word in text for word in ["external cli", "external tool", "cli tool", "bash tool", "bash command"])


def _wants_project_search(text: str) -> bool:
    return any(
        word in text
        for word in [
            "rg",
            "ripgrep",
            "grep",
            "find in files",
            "project search",
            "search project",
            "search code",
            "codebase",
            "repo",
            "repository",
        ]
    )


def _preferred_search_provider(text: str) -> str:
    if "tavily" in text:
        return "tavily"
    if "jina" in text:
        return "jina"
    if "duckduckgo" in text or "ddg" in text:
        return "duckduckgo"
    return "auto"


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


def _plan_markdown(goal: str, plan: List[PlannedStep], revisions: List[Dict[str, Any]] | None = None) -> str:
    lines = [f"# Plan\n\nGoal: {goal}\n", "Mode: plan_execute\n"]
    if revisions:
        lines.append(f"Current revision: {len(revisions) - 1}\n")
    for step in plan:
        lines.append(f"{step.step}. `{step.tool}` ({step.status}) - {step.reason}")
    return "\n".join(lines) + "\n"


def _plan_revision_payload(revision: int, reason: str, plan: List[PlannedStep]) -> Dict[str, Any]:
    return {
        "revision": revision,
        "reason": reason,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "steps": [_step_dict(step) for step in plan],
    }


def _write_execution_state(
    task_path: Path,
    goal: str,
    plan: List[PlannedStep],
    observations: List[Dict[str, Any]],
    plan_revisions: List[Dict[str, Any]],
    phase: str,
    stop_reason: str,
) -> None:
    payload = {
        "mode": "plan_execute",
        "phase": phase,
        "goal": goal,
        "current_step": len(observations) + 1 if phase == "executing" else None,
        "steps_planned": len(plan),
        "steps_executed": len(observations),
        "plan_revision": len(plan_revisions) - 1,
        "stop_reason": stop_reason,
        "plan": [_step_dict(step) for step in plan],
    }
    _safe_write(task_path / "execution_state.json", json.dumps(payload, ensure_ascii=False, indent=2))


def _final_markdown(final: Dict[str, Any], observations: List[Dict[str, Any]]) -> str:
    lines = [
        "# Agent Loop Result",
        "",
        f"- task_id: `{final['task_id']}`",
        f"- goal: {final['goal']}",
        f"- mode: {final['execution']['mode']}",
        f"- stop_reason: {final['execution']['stop_reason']}",
        f"- plan_revisions: {final['execution']['plan_revisions']}",
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
    files = [
        str(task_path / name)
        for name in (
            "goal.md",
            "plan.md",
            "observations.json",
            "tool_calls.jsonl",
            "plan_revisions.jsonl",
            "execution_state.json",
            "final.md",
        )
    ]
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


def _insert_next_step(
    plan: List[PlannedStep],
    observations: List[Dict[str, Any]],
    *,
    status: str,
    tool: str,
    args: Dict[str, Any],
    reason: str,
) -> List[PlannedStep]:
    copied = list(plan)
    insert_at = min(len(observations), len(copied))
    copied.insert(insert_at, PlannedStep(0, status, tool, args, reason))
    return [PlannedStep(index + 1, step.status, step.tool, step.args, step.reason) for index, step in enumerate(copied)]


def _no_more_unexecuted_steps(plan: List[PlannedStep], observations: List[Dict[str, Any]]) -> bool:
    return len(observations) >= len(plan)


def _truncate_json(value: Any, max_chars: int = MAX_RESULT_CHARS) -> Any:
    redacted = _redact_jsonable(value)
    text = json.dumps(redacted, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return redacted
    return {"truncated": True, "preview": _truncate_text(text, max_chars=max_chars)}


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
