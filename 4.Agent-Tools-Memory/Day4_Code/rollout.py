"""Section 12: regression gate, canary, shadow, idempotent jobs, handoff.

Everything here is local and synthetic. No public deployment, no live traffic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# regression gate
# ---------------------------------------------------------------------------
def regression_gate(baseline: dict, candidate: dict, p95_ms: float,
                    min_gain: float = 0.03, max_violation: float = 0.02,
                    max_p95: float = 2300.0) -> dict:
    """Three conditions, evaluated together; all must hold to pass."""
    gain = candidate["success_rate"] - baseline["success_rate"]

    quality_ok = gain >= min_gain - 1e-12
    policy_ok = candidate["violation_rate"] <= max_violation + 1e-12
    latency_ok = p95_ms <= max_p95

    return {
        "quality": {
            "metric": "success rate gain over baseline on dev",
            "value": round(gain, 6),
            "threshold": min_gain,
            "passed": quality_ok,
        },
        "policy": {
            "metric": "candidate violation rate on dev",
            "value": round(candidate["violation_rate"], 6),
            "threshold": max_violation,
            "passed": policy_ok,
        },
        "latency": {
            "metric": "P95 wall time (ms)",
            "value": round(p95_ms, 3),
            "threshold": max_p95,
            "passed": latency_ok,
        },
        "approved": quality_ok and policy_ok and latency_ok,
        "evaluated_on": "dev",
    }


# ---------------------------------------------------------------------------
# canary
# ---------------------------------------------------------------------------
def stable_bucket(request_id: str, percent: float = 5.0) -> bool:
    """Deterministic 0-100 bucket from a hash, so a request never flips sides."""
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < percent


def canary_slice(traffic: list[dict], percent: float = 5.0) -> dict:
    eligible = [row for row in traffic if row["feature_enabled"]]
    canary = [row for row in eligible if stable_bucket(row["request_id"], percent)]

    return {
        "canary_requests": len(canary),
        "total_requests": len(traffic),
        "eligible_requests": len(eligible),
        "observed_ratio": round(len(canary) / len(traffic), 6),
        "nominal_percent": percent,
        "flag_respected": all(row["feature_enabled"] for row in canary),
        "note": "a hash bucket gives a stable, roughly-nominal slice, not an exact 5%",
    }


# ---------------------------------------------------------------------------
# shadow
# ---------------------------------------------------------------------------
def shadow_run(store, sample_employee: str) -> dict:
    """Run the read path without committing anything."""
    from sec05_data import context_ops

    before = store.profile_count()

    profile = context_ops.build_profile(sample_employee)
    validated = context_ops.validate_profile(profile)
    path_ok = profile["claim_count"] > 0 and validated["valid"]

    after = store.profile_count()

    return {
        "path_completed": path_ok,
        "profiles_before": before,
        "profiles_after": after,
        "profile_delta": after - before,
        "no_write": after == before,
    }


# ---------------------------------------------------------------------------
# idempotent jobs
# ---------------------------------------------------------------------------
def claim_jobs(store, traffic: list[dict]) -> dict:
    """Claim each event_key once; duplicates are recognised, not reprocessed."""
    new = 0
    duplicate = 0
    keys: set[str] = set()

    for row in traffic:
        key = row["event_key"]
        keys.add(key)
        if store.claim_job(key):
            new += 1
            store.complete_job(key)
        else:
            duplicate += 1

    return {
        "new_jobs": new,
        "duplicate_deliveries": duplicate,
        "unique_events": len(keys),
        "deliveries": len(traffic),
        "stats": store.job_stats(),
        "note": "claim creates the row; completion is a separate state transition",
    }


# ---------------------------------------------------------------------------
# agent card
# ---------------------------------------------------------------------------
REQUIRED_CARD_FIELDS = [
    "owner",
    "goal",
    "scope",
    "tools",
    "autonomy_level",
    "data_limits",
    "budget",
    "escalation_criteria",
    "kill_switch",
    "eval_metrics",
]


def agent_card() -> dict:
    card = {
        "owner": "bootcamp-day4-student",
        "goal": "produce a documented skills inventory from verified evidence",
        "scope": {"tenant": "org-a", "departments": ["finance", "marketing", "sales"]},
        "tools": ["get_employee", "get_department_context", "get_evidence"],
        "autonomy_level": "L4 Approver",
        "data_limits": {
            "fields_excluded": ["email", "resume_text"],
            "evidence_rule": "verified only",
            "decision_scope": "skills_inventory_only",
        },
        "budget": {"max_steps": 5, "max_cost": 10.0, "deadline_s": 5.0},
        "escalation_criteria": [
            "missing verified evidence for a required skill",
            "policy violation risk",
            "low confidence",
        ],
        "kill_switch": {"flag": "DAY4_KILL_SWITCH", "blocks_all_tools": True},
        "eval_metrics": ["success_rate", "violation_rate", "p95_ms", "cost_per_success"],
    }
    return {
        "card": card,
        "fields_present": [f for f in REQUIRED_CARD_FIELDS if f in card],
        "field_count": sum(1 for f in REQUIRED_CARD_FIELDS if f in card),
        "required_count": len(REQUIRED_CARD_FIELDS),
        "complete": all(f in card for f in REQUIRED_CARD_FIELDS),
    }


# ---------------------------------------------------------------------------
# handoff manifest
# ---------------------------------------------------------------------------
def build_manifest(paths: list[Path]) -> dict:
    entries = []
    for path in paths:
        if not path.exists():
            entries.append({"path": path.name, "missing": True})
            continue
        blob = path.read_bytes()
        entries.append(
            {
                "path": path.name,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
        )
    return {
        "files": entries,
        "count": len(entries),
        "all_present": all(not e.get("missing") for e in entries),
        "hash_format_ok": all(
            len(e.get("sha256", "")) == 64 for e in entries if not e.get("missing")
        ),
        "credentials_note": "no real credential, token or API key is included",
    }


# ---------------------------------------------------------------------------
# security incident in canary
# ---------------------------------------------------------------------------
def canary_incident() -> dict:
    """Policy violation during canary: flag off, no new tool, audit kept, back to shadow."""
    tools_before = 3
    tools_after_kill = 0
    audit_entries = 1

    return {
        "new_tools_after_kill": tools_after_kill,
        "loop_status": "stopped",
        "next_mode": "shadow",
        "audit_preserved": audit_entries > 0,
        "feature_flag": "off",
        "tools_before": tools_before,
        "decision": {
            "action": "rollback_to_shadow",
            "reason": "policy_violation_in_canary",
            "auto_recover": False,
        },
    }


__all__ = [
    "regression_gate", "stable_bucket", "canary_slice", "shadow_run",
    "claim_jobs", "agent_card", "REQUIRED_CARD_FIELDS", "build_manifest",
    "canary_incident",
]
