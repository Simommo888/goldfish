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
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Protocol
from uuid import uuid4

from .agent_memory import load_memory, memory_context
from .config_loader import load_config
from .model_setup import redact_secret_text
from .providers.registry import get_provider, resolve_llm_connection
from .response_formatter import render_agent_summary
from .skill_router import select_skills
from .utils import kb_root, now, safe_filename


ALLOWED_TOOLS = {
    "web_search",
    "knowledge_lookup",
    "search",
    "rag_query",
    "rag_search",
    "rag_status",
    "memory_show",
    "tools",
    "doctor",
    "dry_run",
    "run_daily",
    "external_cli",
    "skills",
}
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


@dataclass(frozen=True)
class AgentFailurePolicy:
    """Bounded execution policy for the local plan/execute loop.

    The loop only calls allow-listed ToolRegistry tools, but individual tools can
    still fail, stall on network I/O, or return degraded results. This policy is
    the agent-level guardrail that decides how long to wait and when to stop.
    """

    step_timeout_seconds: float = 45.0
    task_timeout_seconds: float = 240.0
    max_total_failures: int = 4
    max_consecutive_failures: int = 2
    step_timeout_overridden: bool = False


def run_agent_loop(
    goal: str,
    *,
    registry: RegistryLike,
    max_steps: int = 5,
    no_llm: bool = False,
    no_save: bool = False,
    root: Path | None = None,
    step_timeout: float | None = None,
    task_timeout: float | None = None,
    max_failures: int | None = None,
    max_consecutive_failures: int | None = None,
) -> Dict[str, Any]:
    """Run a bounded plan/execute loop and return a structured result."""

    root = root or kb_root()
    clean_goal = redact_secret_text(goal.strip())
    policy = _resolve_failure_policy(
        step_timeout=step_timeout,
        task_timeout=task_timeout,
        max_failures=max_failures,
        max_consecutive_failures=max_consecutive_failures,
    )
    started_perf = time.perf_counter()
    started_at = datetime.now().isoformat(timespec="seconds")
    task = _create_task_workspace(root, clean_goal)
    step_limit = max(1, min(max_steps, 8))
    selected_skills = select_skills(clean_goal)
    memory_note = memory_context(load_memory(root), max_items=8)
    plan = make_plan(clean_goal, max_steps=step_limit, no_save=no_save, selected_skills=selected_skills)
    plan_revisions = [_plan_revision_payload(0, "initial plan", plan)]
    observations: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []
    stop_reason = "plan_complete"

    _safe_write(task["path"] / "goal.md", f"# Goal\n\n{clean_goal}\n")
    _safe_write(task["path"] / "selected_skills.json", json.dumps(selected_skills, ensure_ascii=False, indent=2))
    _safe_write(task["path"] / "skills.md", _skills_markdown(selected_skills))
    _safe_write(task["path"] / "memory_context.md", memory_note + "\n")
    _safe_write(task["path"] / "failure_policy.json", json.dumps(_policy_dict(policy), ensure_ascii=False, indent=2))
    _safe_write(task["path"] / "plan.md", _plan_markdown(clean_goal, plan))
    _append_jsonl(task["path"] / "plan_revisions.jsonl", plan_revisions[0])
    _write_execution_state(task["path"], clean_goal, plan, observations, plan_revisions, "planning", "", selected_skills, policy, started_at)

    cursor = 0
    while cursor < len(plan) and len(observations) < step_limit:
        if _task_timed_out(started_perf, policy):
            stop_reason = "task_timeout_reached"
            break
        planned = plan[cursor]
        _write_execution_state(task["path"], clean_goal, plan, observations, plan_revisions, "executing", f"step-{planned.step}", selected_skills, policy, started_at)
        effective_timeout = _effective_step_timeout(policy, registry, planned.tool, started_perf)
        observation = _execute_step(planned, registry, timeout_seconds=effective_timeout)
        observations.append(observation)
        tool_calls.append(
            {
                "step": planned.step,
                "tool": planned.tool,
                "args": _redact_jsonable(planned.args),
                "success": observation.get("success", False),
                "status": planned.status,
                "duration_ms": observation.get("duration_ms"),
                "timeout_seconds": observation.get("timeout_seconds"),
                "timed_out": observation.get("timed_out", False),
                "failure_type": observation.get("failure_type"),
            }
        )
        _append_jsonl(task["path"] / "tool_calls.jsonl", tool_calls[-1])
        _safe_write(task["path"] / "observations.json", json.dumps(observations, ensure_ascii=False, indent=2))

        decision = _decide_next(
            clean_goal,
            plan,
            observations,
            step_limit=step_limit,
            no_save=no_save,
            policy=policy,
            started_perf=started_perf,
        )
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

    failure_summary = _failure_summary(observations)
    files_written = _collect_files_written(task["path"], observations)
    summary = _final_answer(clean_goal, plan, observations, no_llm=no_llm, files_written=files_written)
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
            "started_at": started_at,
            "duration_ms": _elapsed_ms(started_perf),
            "failure_policy": _policy_dict(policy),
            "failure_summary": failure_summary,
        },
        "selected_skills": selected_skills,
    }

    _safe_write(task["path"] / "observations.json", json.dumps(observations, ensure_ascii=False, indent=2))
    _write_execution_state(task["path"], clean_goal, plan, observations, plan_revisions, "final", stop_reason, selected_skills, policy, started_at)
    _safe_write(task["path"] / "final.md", _final_markdown(final, observations))

    return {
        "status": "ok",
        "task_id": task["id"],
        "task_path": str(task["path"]),
        "goal": clean_goal,
        "plan": [_step_dict(step) for step in plan],
        "selected_skills": selected_skills,
        "observations": observations,
        "plan_revisions": plan_revisions,
        "execution": final["execution"],
        "failure_policy": _policy_dict(policy),
        "failure_summary": failure_summary,
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


def make_plan(
    goal: str,
    *,
    max_steps: int = 5,
    no_save: bool = False,
    selected_skills: List[Dict[str, Any]] | None = None,
) -> List[PlannedStep]:
    lowered = goal.lower()
    steps: List[PlannedStep] = []
    selected_skills = selected_skills or []

    if selected_skills:
        primary = selected_skills[0]
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "reading",
                "skills",
                {"name": primary["name"]},
                f"Load selected skill guidance: {primary['name']}.",
            )
    )

    if _wants_doctor(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "doctor", {}, "Goal asks to inspect runtime/config health."))
    if _wants_tools(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "tools", {}, "Goal asks about available capabilities."))
    if _wants_external_cli(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "external_cli", {"action": "list"}, "Goal asks about external CLI tools."))
    if _wants_memory(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "memory_show", {}, "Goal asks to inspect memory."))
    if _wants_rag_status(lowered):
        steps.append(PlannedStep(len(steps) + 1, "reading", "rag_status", {}, "Goal asks to inspect local RAG service health."))

    knowledge_lookup_added = False
    if _wants_knowledge_lookup(lowered):
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "search",
                "knowledge_lookup",
                {"query": _strip_knowledge_lookup_words(goal), "top_k": 8, "web_limit": 5},
                "Goal asks for a local-first lookup; query RAG first, then public web in separate blocks.",
            )
        )
        knowledge_lookup_added = True

    if not knowledge_lookup_added and _wants_rag_query(lowered):
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "search",
                "rag_query",
                {"question": _strip_rag_words(goal), "top_k": 8},
                "Goal asks for local RAG/Obsidian knowledge-base context.",
            )
        )
    if not knowledge_lookup_added and _wants_local_search(lowered):
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "search",
                "search",
                {"query": _strip_intent_words(goal), "limit": 8},
                "Goal asks for local/history/notes search.",
            )
        )
    if not knowledge_lookup_added and _wants_web_search(lowered):
        steps.append(
            PlannedStep(
                len(steps) + 1,
                "search",
                "web_search",
                {
                    "query": _strip_intent_words(goal),
                    "limit": 8,
                    "search_provider": _preferred_search_provider(lowered),
                },
                "Goal asks for public web search results without a full research report.",
            )
        )
    if not knowledge_lookup_added and (_wants_research(lowered) or _skills_include(selected_skills, {"web-research", "internet-search", "business-idea", "trend-analysis"})):
        if any(step.tool == "web_search" for step in steps) and not _skills_include(selected_skills, {"web-research", "business-idea", "trend-analysis"}):
            pass
        else:
            steps.append(
                PlannedStep(
                    len(steps) + 1,
                    "search",
                    "web_search",
                    {
                        "query": _strip_intent_words(goal),
                        "mode": "research",
                        "limit": 5,
                        "fetch_limit": 3,
                        "no_llm": True,
                        "no_save": no_save,
                        "search_provider": _preferred_search_provider(lowered),
                    },
                    "Goal asks for public web research or market/trend/opportunity study.",
                )
            )
    if not knowledge_lookup_added and (_wants_local_search(lowered) or _skills_include(selected_skills, {"retrieval-planning", "knowledge-routing", "draft-writing"})):
        if not any(step.tool == "search" for step in steps):
            steps.append(
                PlannedStep(
                    len(steps) + 1,
                    "search",
                    "search",
                    {"query": _strip_intent_words(goal), "limit": 8},
                    "Selected skills need local/history/notes context.",
                )
            )

    if _wants_daily(lowered) or _skills_include(selected_skills, {"weekly-review"}):
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
    policy: AgentFailurePolicy,
    started_perf: float,
) -> Dict[str, Any]:
    """Decide whether to continue, revise, or stop after an observation."""

    if not observations:
        return {"action": "continue", "reason": "no observations yet", "plan": plan}

    if _task_timed_out(started_perf, policy):
        return {"action": "stop", "reason": "task_timeout_reached", "plan": plan}

    if len(observations) >= step_limit:
        return {"action": "stop", "reason": "max_steps_reached", "plan": plan}

    last = observations[-1]
    failures = _failure_summary(observations)
    if failures["total_failures"] >= policy.max_total_failures:
        return {"action": "stop", "reason": "max_total_failures_reached", "plan": plan}
    if failures["consecutive_failures"] >= policy.max_consecutive_failures:
        return {"action": "stop", "reason": "max_consecutive_failures_reached", "plan": plan}

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

    if last.get("tool") == "knowledge_lookup" and not last.get("success") and "search" not in used_tools | planned_tools:
        new_plan = _insert_next_step(
            plan,
            observations,
            status="search",
            tool="search",
            args={"query": _strip_knowledge_lookup_words(goal), "limit": 8},
            reason="Combined RAG/web lookup failed; fall back to local goldfish history search.",
        )
        return {"reason": "knowledge_lookup_failed_add_local_search", "plan": new_plan}

    if last.get("tool") == "web_search" and not last.get("success") and "search" not in used_tools | planned_tools:
        new_plan = _insert_next_step(
            plan,
            observations,
            status="search",
            tool="search",
            args={"query": _strip_intent_words(goal), "limit": 8},
            reason="Web research failed or degraded; fall back to local history search.",
        )
        return {"reason": "web_search_failed_add_local_search", "plan": new_plan}

    if last.get("tool") == "rag_query" and not last.get("success") and "search" not in used_tools | planned_tools:
        new_plan = _insert_next_step(
            plan,
            observations,
            status="search",
            tool="search",
            args={"query": _strip_rag_words(goal), "limit": 8},
            reason="RAG query failed or service is unavailable; fall back to local goldfish search.",
        )
        return {"reason": "rag_query_failed_add_local_search", "plan": new_plan}

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


def _resolve_failure_policy(
    *,
    step_timeout: float | None = None,
    task_timeout: float | None = None,
    max_failures: int | None = None,
    max_consecutive_failures: int | None = None,
) -> AgentFailurePolicy:
    try:
        settings = load_config().settings
    except Exception:
        settings = {}
    step_overridden = step_timeout is not None
    return AgentFailurePolicy(
        step_timeout_seconds=_float_range(
            step_timeout if step_timeout is not None else settings.get("agent_step_timeout_seconds", 45),
            45.0,
            min_value=0.05,
            max_value=600.0,
        ),
        task_timeout_seconds=_float_range(
            task_timeout if task_timeout is not None else settings.get("agent_task_timeout_seconds", 240),
            240.0,
            min_value=5.0,
            max_value=7200.0,
        ),
        max_total_failures=_int_range(
            max_failures if max_failures is not None else settings.get("agent_max_total_failures", 4),
            4,
            min_value=1,
            max_value=20,
        ),
        max_consecutive_failures=_int_range(
            max_consecutive_failures if max_consecutive_failures is not None else settings.get("agent_max_consecutive_failures", 2),
            2,
            min_value=1,
            max_value=10,
        ),
        step_timeout_overridden=step_overridden,
    )


def _policy_dict(policy: AgentFailurePolicy) -> Dict[str, Any]:
    return {
        "step_timeout_seconds": policy.step_timeout_seconds,
        "task_timeout_seconds": policy.task_timeout_seconds,
        "max_total_failures": policy.max_total_failures,
        "max_consecutive_failures": policy.max_consecutive_failures,
        "step_timeout_overridden": policy.step_timeout_overridden,
    }


def _effective_step_timeout(policy: AgentFailurePolicy, registry: RegistryLike, tool_name: str, started_perf: float) -> float:
    timeout = policy.step_timeout_seconds
    if not policy.step_timeout_overridden:
        tool_timeout = _registry_tool_timeout(registry, tool_name)
        if tool_timeout is not None:
            timeout = tool_timeout
    remaining = _remaining_task_seconds(started_perf, policy)
    if remaining is not None:
        timeout = min(timeout, remaining)
    return max(0.001, timeout)


def _registry_tool_timeout(registry: RegistryLike, tool_name: str) -> float | None:
    tools = getattr(registry, "tools", None)
    if not isinstance(tools, dict):
        return None
    spec = tools.get(tool_name)
    value = getattr(spec, "timeout_seconds", None)
    if value is None:
        return None
    return _float_range(value, 45.0, min_value=0.05, max_value=600.0)


def _remaining_task_seconds(started_perf: float, policy: AgentFailurePolicy) -> float | None:
    if policy.task_timeout_seconds <= 0:
        return None
    return max(0.0, policy.task_timeout_seconds - (time.perf_counter() - started_perf))


def _task_timed_out(started_perf: float, policy: AgentFailurePolicy) -> bool:
    remaining = _remaining_task_seconds(started_perf, policy)
    return remaining is not None and remaining <= 0


def _failure_summary(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    failures = [obs for obs in observations if not obs.get("success")]
    consecutive = 0
    for obs in reversed(observations):
        if obs.get("success"):
            break
        consecutive += 1
    return {
        "total_failures": len(failures),
        "consecutive_failures": consecutive,
        "timeouts": sum(1 for obs in failures if obs.get("failure_type") == "timeout" or obs.get("timed_out")),
        "tool_errors": sum(1 for obs in failures if obs.get("failure_type") == "tool_error"),
        "exceptions": sum(1 for obs in failures if obs.get("failure_type") == "exception"),
    }


def _elapsed_ms(started_perf: float) -> int:
    return int((time.perf_counter() - started_perf) * 1000)


def _float_range(value: Any, default: float, *, min_value: float, max_value: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = default
    return max(min_value, min(max_value, number))


def _int_range(value: Any, default: int, *, min_value: int, max_value: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(min_value, min(max_value, number))


def _execute_step(step: PlannedStep, registry: RegistryLike, *, timeout_seconds: float) -> Dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    started_perf = time.perf_counter()
    base = {
        "step": step.step,
        "status": step.status,
        "tool": step.tool,
        "reason": step.reason,
        "started_at": started_at,
        "attempt": 1,
        "timeout_seconds": round(timeout_seconds, 3),
        "_started_perf": started_perf,
    }
    if step.tool not in ALLOWED_TOOLS:
        return _finish_observation(
            base,
            success=False,
            error="tool is not allow-listed",
            failure_type="not_allow_listed",
        )
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"goldfish-{step.tool}")
    try:
        future = executor.submit(registry.execute, step.tool, step.args)
        result = future.result(timeout=max(0.001, timeout_seconds))
        return _finish_observation(
            base,
            success=result.get("status", "ok") != "error",
            result=_truncate_json(result),
            failure_type="tool_error" if result.get("status") == "error" else None,
            error=result.get("error") if isinstance(result, dict) and result.get("status") == "error" else None,
        )
    except FutureTimeoutError:
        return _finish_observation(
            base,
            success=False,
            error=f"tool timed out after {round(timeout_seconds, 3)}s",
            failure_type="timeout",
            timed_out=True,
        )
    except Exception as exc:
        return _finish_observation(
            base,
            success=False,
            error=str(exc),
            failure_type="exception",
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _finish_observation(base: Dict[str, Any], **updates: Any) -> Dict[str, Any]:
    started_perf = float(base.get("_started_perf") or time.perf_counter())
    payload = {key: value for key, value in base.items() if not key.startswith("_")}
    payload.update({key: value for key, value in updates.items() if value is not None})
    payload.setdefault("timed_out", False)
    payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
    payload["duration_ms"] = _elapsed_ms(started_perf)
    if not payload.get("success") and "failure_type" not in payload:
        payload["failure_type"] = "tool_error"
    return payload


def _final_answer(
    goal: str,
    plan: List[PlannedStep],
    observations: List[Dict[str, Any]],
    *,
    no_llm: bool,
    files_written: List[str] | None = None,
) -> Dict[str, Any]:
    rule_answer = _rule_final(goal, observations, files_written=files_written)
    if no_llm:
        return rule_answer
    config = load_config()
    connection = resolve_llm_connection(config.settings)
    if not connection.get("api_key"):
        return rule_answer
    prompt = (
        "You are goldfish's local agent loop. Summarize the completed tool observations. "
        "Do not invent sources, files, or API keys. Return concise JSON with keys summary and next_actions. "
        "The summary value must be Markdown following the fixed Goldfish answer frame: "
        "header, conclusion, execution record, key observations, products, next actions."
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


def _rule_final(goal: str, observations: List[Dict[str, Any]], *, files_written: List[str] | None = None) -> Dict[str, Any]:
    next_actions = [
        "Review the task workspace observations.",
        "Open any generated Markdown reports or drafts before treating them as final.",
        "Run a more specific /agent goal if you want a narrower follow-up.",
    ]
    if _wants_research(goal.lower()):
        next_actions.insert(0, "Verify high-value web sources before converting them into permanent notes or business ideas.")
    summary = render_agent_summary(goal, observations, next_actions[:5], files_written=files_written)
    return {"summary": summary, "next_actions": next_actions[:5]}


def _skills_include(selected_skills: List[Dict[str, Any]], names: set[str]) -> bool:
    return any(str(skill.get("name", "")) in names for skill in selected_skills)


def _wants_external_cli(text: str) -> bool:
    return any(word in text for word in ["external cli", "external tool", "cli tool", "bash tool", "bash command"])


def _wants_web_search(text: str) -> bool:
    return any(
        word in text
        for word in [
            "web search",
            "internet search",
            "online search",
            "search web",
            "search the web",
            "联网搜索",
            "全网搜索",
            "网页搜索",
            "搜索网页",
            "查网页",
        ]
    )


def _wants_knowledge_lookup(text: str) -> bool:
    if _wants_rag_query(text) or _wants_rag_status(text):
        return False
    if _wants_web_search(text):
        return False
    if any(
        marker in text
        for marker in [
            "latest",
            "today",
            "breaking",
            "news",
            "real-time",
            "realtime",
            "最新",
            "实时",
            "今天",
            "今日",
            "新闻",
            "消息",
            "大事",
            "动态",
        ]
    ):
        return False
    return any(
        marker in text
        for marker in [
            "look up",
            "lookup",
            "find out",
            "query",
            "查一下",
            "查找",
            "查询",
            "检索",
            "搜一下",
            "搜索一下",
            "找一下",
            "相关内容",
            "相关资料",
            "相关笔记",
        ]
    )


def _strip_knowledge_lookup_words(goal: str) -> str:
    cleaned = re.sub(
        r"\b(look up|lookup|find out|query|please|help me|can you|could you)\b",
        " ",
        goal,
        flags=re.I,
    )
    for marker in [
        "帮我",
        "请帮我",
        "麻烦",
        "查一下",
        "查找",
        "查询",
        "检索",
        "搜一下",
        "搜索一下",
        "找一下",
        "相关内容",
        "相关资料",
        "相关笔记",
        "内容",
    ]:
        cleaned = cleaned.replace(marker, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:，,。.!！?？")
    return cleaned or goal.strip()


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
    if any(word in text for word in ["latest", "today", "breaking", "real-time", "realtime", "news", "最新", "实时", "今天", "新闻", "消息"]):
        return "news"
    if "duckduckgo" in text or "ddg" in text:
        return "duckduckgo"
    return "auto"


def _wants_rag_status(text: str) -> bool:
    return any(
        word in text
        for word in [
            "rag status",
            "rag health",
            "rag service",
            "knowledge base status",
            "知识库状态",
            "rag状态",
            "rag服务",
        ]
    )


def _wants_rag_query(text: str) -> bool:
    return any(
        word in text
        for word in [
            "rag knowledge base",
            "local rag",
            "local knowledge base",
            "my knowledge base",
            "obsidian",
            "saved notes",
            "previous notes",
            "knowledge base notes",
            "本地知识库",
            "我的知识库",
            "rag知识库",
            "rag 知识库",
            "知识库里",
            "知识库中",
            "之前的笔记",
            "已有笔记",
            "沉淀内容",
        ]
    )


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


def _skills_markdown(selected_skills: List[Dict[str, Any]]) -> str:
    if not selected_skills:
        return "# Selected Skills\n\nNo skill matched this goal.\n"
    lines = ["# Selected Skills", ""]
    for index, skill in enumerate(selected_skills, start=1):
        lines.extend(
            [
                f"## {index}. {skill.get('name', 'unknown')}",
                "",
                f"- title: {skill.get('title', '')}",
                f"- path: {skill.get('path', '')}",
                f"- reason: {skill.get('reason', '')}",
                f"- matched_keywords: {', '.join(str(item) for item in skill.get('matched_keywords', []))}",
                "",
                "### Preview",
                "",
                str(skill.get("content_preview", "")),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


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
    selected_skills: List[Dict[str, Any]] | None = None,
    policy: AgentFailurePolicy | None = None,
    started_at: str | None = None,
) -> None:
    payload = {
        "mode": "plan_execute",
        "phase": phase,
        "goal": goal,
        "started_at": started_at,
        "selected_skills": [{"name": skill.get("name"), "reason": skill.get("reason")} for skill in (selected_skills or [])],
        "current_step": len(observations) + 1 if phase == "executing" else None,
        "steps_planned": len(plan),
        "steps_executed": len(observations),
        "plan_revision": len(plan_revisions) - 1,
        "stop_reason": stop_reason,
        "failure_policy": _policy_dict(policy) if policy else None,
        "failure_summary": _failure_summary(observations),
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
        f"- duration_ms: {final['execution'].get('duration_ms')}",
        f"- failures: {final['execution'].get('failure_summary', {}).get('total_failures', 0)} total / {final['execution'].get('failure_summary', {}).get('consecutive_failures', 0)} consecutive",
        "",
        "## Selected Skills",
        "",
    ]
    selected_skills = final.get("selected_skills", [])
    if selected_skills:
        lines.extend(f"- `{skill.get('name')}` - {skill.get('reason')}" for skill in selected_skills)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            final["summary"],
            "",
            "## Next Actions",
            "",
        ]
    )
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
            "skills.md",
            "selected_skills.json",
            "memory_context.md",
            "failure_policy.json",
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


def _strip_rag_words(goal: str) -> str:
    cleaned = re.sub(
        r"\b(rag knowledge base|local rag|local knowledge base|my knowledge base|obsidian|saved notes|previous notes|knowledge base notes|please|help me)\b",
        " ",
        goal,
        flags=re.I,
    )
    for marker in ["本地知识库", "我的知识库", "rag知识库", "RAG知识库", "rag 知识库", "RAG 知识库", "知识库里", "知识库中", "之前的笔记", "已有笔记", "沉淀内容"]:
        cleaned = cleaned.replace(marker, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:，,")
    return cleaned or goal.strip()
