"""The bounded tool loop: offline decision model, guards, traces and gates.

Every guard is checked *before* the tool has any effect:
  step cap -> budget -> repetition fingerprint -> deadline -> kill switch -> tool

The decision model is an offline fixture (deterministic), never a live LLM. Section
6.11 and 12.10 both require that distinction to be stated, so `EXECUTION_SCOPE`
records it explicitly.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "Day4_Code"))

from common import data, principal  # noqa: E402
from toolset import (  # noqa: E402
    ToolValidationError,
    call_tool,
    validate_arguments,
)

DECISION_SCOPE = "skills_inventory_only"

EXECUTION_SCOPE = {
    "real": [
        "sqlite",
        "mcp_stdio",
        "langgraph",
        "tool_dispatch",
        "loop_guards",
        "router_training",
        "evaluation_metrics",
    ],
    "fixture": [
        "decision_model",
        "reviewer_identity",
        "comparison_logs",
        "model_responses",
    ],
    "not_executed": [
        "live_llm",
        "public_deployment",
        "external_auth",
        "a2a_protocol",
    ],
}

# ---------------------------------------------------------------------------
# action union
# ---------------------------------------------------------------------------
def make_tool_action(name: str, arguments: dict) -> dict:
    return {"kind": "tool", "name": name, "arguments": arguments}


def make_final_action(text: str) -> dict:
    return {"kind": "final", "text": text}


class ActionError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def validate_action(action: object) -> dict:
    """Validate the tool/final union before anything else looks at it."""
    if not isinstance(action, dict):
        raise ActionError("action must be an object", code="not_object")

    kind = action.get("kind")
    if kind not in {"tool", "final"}:
        raise ActionError(f"unknown action kind {kind!r}", code="unknown_kind")

    if kind == "tool":
        name = action.get("name")
        if not isinstance(name, str) or not name:
            raise ActionError("tool action needs a name", code="missing_name")
        arguments = action.get("arguments")
        if not isinstance(arguments, dict):
            raise ActionError("tool action needs an arguments object", code="bad_arguments")
        return action

    text = action.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ActionError("final action needs non-empty text", code="empty_final")
    return action


def validate_output_profile(payload: dict) -> dict:
    """Reject a syntactically valid final whose content is out of scope."""
    if not isinstance(payload, dict):
        raise ActionError("profile must be an object", code="not_object")
    decision = payload.get("decision")
    if decision != DECISION_SCOPE:
        raise ActionError(
            f"decision must be {DECISION_SCOPE!r}, got {decision!r}",
            code="decision_out_of_scope",
        )
    return payload


# ---------------------------------------------------------------------------
# offline decision model (fixture)
# ---------------------------------------------------------------------------
class OfflineDecisionModel:
    """Deterministic decider: replays `model_responses.jsonl`, never calls an LLM."""

    mode = "fixture"

    def __init__(self, employee_id: str, script: list[dict] | None = None) -> None:
        self.employee_id = employee_id
        self.script = script or []
        self.index = 0

    def next_action(self, observations: list[dict]) -> dict:
        if self.index >= len(self.script):
            return make_final_action("")
        action = self.script[self.index]
        self.index += 1
        return action


class RepeatingModel:
    """Always returns the same tool call -- used to prove loop detection."""

    mode = "fixture"

    def __init__(self, employee_id: str) -> None:
        self.action = make_tool_action("get_employee", {"employee_id": employee_id})
        self.calls = 0

    def next_action(self, observations: list[dict]) -> dict:
        self.calls += 1
        return dict(self.action)


class SlowModel:
    """Sleeps to simulate latency, so the deadline guard can be exercised."""

    mode = "fixture"

    def __init__(self, delay: float, action: dict) -> None:
        self.delay = delay
        self.action = action

    def next_action(self, observations: list[dict]) -> dict:
        time.sleep(self.delay)
        return self.action


def action_fingerprint(action: dict) -> str:
    """Identity of an action: same tool + same arguments means the same effect."""
    blob = json.dumps(
        {"name": action.get("name"), "arguments": action.get("arguments")},
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# ---------------------------------------------------------------------------
# retry policy
# ---------------------------------------------------------------------------
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def retry_plan(
    statuses: Iterable[int],
    retry_after_ms: dict[int, int] | None = None,
    max_attempts: int = 3,
    base_backoff_ms: int = 100,
) -> dict:
    """Plan retries without sleeping. Only retryable statuses are tried again."""
    retry_after_ms = retry_after_ms or {}
    attempts = 0
    total_wait = 0
    final_status = None

    for status in statuses:
        attempts += 1
        final_status = status
        if status not in RETRYABLE_STATUS:
            break
        if attempts >= max_attempts:
            break
        wait = retry_after_ms.get(status)
        if wait is None:
            wait = base_backoff_ms * (2 ** (attempts - 1))
        total_wait += min(wait, 2000)  # bounded backoff

    return {
        "attempts": attempts,
        "total_wait_ms": total_wait,
        "final_status": final_status,
        "retryable_final": final_status in RETRYABLE_STATUS,
    }


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------
@dataclass
class LoopLimits:
    max_steps: int = 5
    budget: float = 10.0
    deadline_s: float = 5.0
    kill_switch: bool = False


@dataclass
class LoopResult:
    status: str
    reason: str
    steps: int = 0
    tool_calls: int = 0
    cost: float = 0.0
    final: str | None = None
    trace: list[dict] = field(default_factory=list)
    rejected: int = 0
    successful_tools: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "cost": round(self.cost, 6),
            "final": self.final,
            "rejected": self.rejected,
            "successful_tools": self.successful_tools,
            "trace": self.trace,
            "trajectory": [s.get("tool") for s in self.trace if s.get("kind") == "tool"],
        }


STEP_COST = 1.0


def run_loop(
    model,
    caller: principal.Principal,
    limits: LoopLimits,
    observation_sink: list[dict] | None = None,
) -> LoopResult:
    """Run the guarded loop. Guards run before each tool effect."""
    result = LoopResult(status="running", reason="")
    observations: list[dict] = []
    seen_fingerprints: set[str] = set()
    started = time.monotonic()

    while True:
        # 1. step cap
        if result.steps >= limits.max_steps:
            result.status, result.reason = "stopped", "step_cap"
            break

        # 2. cost budget, checked before the call
        if result.cost + STEP_COST > limits.budget:
            result.status, result.reason = "stopped", "budget_exhausted"
            break

        # 3. deadline, checked before asking the model
        if time.monotonic() - started > limits.deadline_s:
            result.status, result.reason = "stopped", "deadline_exceeded"
            break

        # 4. kill switch
        if limits.kill_switch:
            result.status, result.reason = "stopped", "kill_switch"
            break

        action = model.next_action(observations)
        result.steps += 1

        try:
            validate_action(action)
        except ActionError as error:
            result.rejected += 1
            result.trace.append({"kind": "rejected", "code": error.code,
                                 "step": result.steps})
            result.status, result.reason = "rejected", error.code
            break

        if action["kind"] == "final":
            result.final = action["text"]
            result.trace.append({"kind": "final", "step": result.steps})
            result.status, result.reason = "completed", "final"
            break

        # ---- tool branch: every guard before the effect -------------------
        try:
            validate_arguments(action["name"], action["arguments"])
        except ToolValidationError as error:
            result.rejected += 1
            result.trace.append({"kind": "rejected", "code": error.code,
                                 "step": result.steps, "tool": action.get("name")})
            result.status, result.reason = "rejected", error.code
            break

        fingerprint = action_fingerprint(action)
        if fingerprint in seen_fingerprints:
            result.trace.append({"kind": "stopped", "code": "repeated_action",
                                 "step": result.steps, "tool": action["name"]})
            result.status, result.reason = "stopped", "repeated_action"
            break

        # deadline again: the model call may have burned the budget
        if time.monotonic() - started > limits.deadline_s:
            result.trace.append({"kind": "stopped", "code": "deadline_exceeded",
                                 "step": result.steps, "tool": action["name"]})
            result.status, result.reason = "stopped", "deadline_exceeded"
            break

        try:
            observation = call_tool(action["name"], action["arguments"], caller)
        except (ToolValidationError, principal.ScopeError) as error:
            result.rejected += 1
            code = getattr(error, "code", "tool_error")
            result.trace.append({"kind": "rejected", "code": code,
                                 "step": result.steps, "tool": action["name"]})
            result.status, result.reason = "rejected", code
            break

        seen_fingerprints.add(fingerprint)
        result.tool_calls += 1
        result.successful_tools += 1
        result.cost += STEP_COST
        observations.append(observation)
        result.trace.append(
            {"kind": "tool", "step": result.steps, "tool": action["name"],
             "arguments": action["arguments"]}
        )

    if observation_sink is not None:
        observation_sink.extend(observations)
    return result


# ---------------------------------------------------------------------------
# trajectory gate and kill switch
# ---------------------------------------------------------------------------
def trajectory_gate(trace: list[dict], expected: list[str]) -> dict:
    actual = [s["tool"] for s in trace if s.get("kind") == "tool"]
    return {
        "compliant": actual == expected,
        "expected": expected,
        "actual": actual,
        "step_count": len(actual),
    }


def kill_switch_test(model_factory: Callable[[], object], caller,
                     limits: LoopLimits) -> dict:
    """Prove no tool runs when the switch is off."""
    model = model_factory()
    result = run_loop(model, caller, LoopLimits(
        max_steps=limits.max_steps, budget=limits.budget,
        deadline_s=limits.deadline_s, kill_switch=True,
    ))
    return {
        "status": result.status,
        "reason": result.reason,
        "tools_executed": result.tool_calls,
        "blocked": result.tool_calls == 0,
    }


def final_acceptance_gate(result: LoopResult, profile: dict | None) -> dict:
    """A completed loop is not the same as an accepted answer."""
    conditions = {
        "completed": result.status == "completed",
        "path_allowed": all(
            s.get("kind") in {"tool", "final"} for s in result.trace
        ),
        "grounded": profile is not None,
    }
    if profile is not None:
        try:
            validate_output_profile(profile)
            conditions["in_scope"] = True
        except ActionError:
            conditions["in_scope"] = False
    return {
        "accepted": all(conditions.values()),
        "conditions": conditions,
        "final_reached": result.status == "completed",
    }


__all__ = [
    "DECISION_SCOPE", "EXECUTION_SCOPE", "LoopLimits", "LoopResult",
    "OfflineDecisionModel", "RepeatingModel", "SlowModel",
    "make_tool_action", "make_final_action", "validate_action",
    "validate_output_profile", "action_fingerprint", "retry_plan",
    "RETRYABLE_STATUS", "run_loop", "trajectory_gate", "kill_switch_test",
    "final_acceptance_gate", "ActionError",
]
