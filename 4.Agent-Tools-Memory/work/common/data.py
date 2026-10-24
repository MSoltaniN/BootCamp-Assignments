"""Loaders for every Day 4 dataset, with light caching.

The assignment re-reads the same eight files in almost every section, so each
loader caches its result. Data is read-only; nothing here mutates the pack.

Usage
-----
    from common import data

    people = data.people()                 # list[dict], 180 records
    docs = data.documents()                # list[dict], 96 records
    by_id = data.people_by_id()            # dict[employee_id, dict]
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

from . import paths


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# 01_HR
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def people() -> list[dict]:
    return _read_jsonl(paths.PEOPLE)


@lru_cache(maxsize=1)
def people_by_id() -> dict[str, dict]:
    return {person["employee_id"]: person for person in people()}


@lru_cache(maxsize=1)
def department_context() -> list[dict]:
    return _read_jsonl(paths.DEPARTMENT_CONTEXT)


@lru_cache(maxsize=1)
def policy_by_scope() -> dict[tuple[str, str], dict]:
    """Key policies by (tenant, department) -- the assignment's access boundary."""
    return {
        (policy["tenant"], policy["department"]): policy
        for policy in department_context()
    }


# ---------------------------------------------------------------------------
# 02_Context
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def documents() -> list[dict]:
    return _read_jsonl(paths.DOCUMENTS)


@lru_cache(maxsize=1)
def budget_parts() -> list[dict]:
    rows = _read_csv(paths.BUDGET_PARTS)
    for row in rows:
        row["estimated_tokens"] = int(row["estimated_tokens"])
        row["priority"] = int(row["priority"])
        row["mandatory"] = str(row["mandatory"]).strip().lower() in {"true", "1", "yes"}
    return rows


# ---------------------------------------------------------------------------
# 03_Requests
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def requests() -> list[dict]:
    return _read_jsonl(paths.REQUESTS_FILE)


@lru_cache(maxsize=1)
def labels() -> list[dict]:
    return _read_jsonl(paths.LABELS)


@lru_cache(maxsize=1)
def labels_by_id() -> dict[str, dict]:
    return {row["request_id"]: row for row in labels()}


def requests_by_split(split: str) -> list[dict]:
    return [row for row in requests() if row["split"] == split]


def labelled_requests(split: str) -> list[dict]:
    """Join requests with their train/dev label. Test has no label in the pack."""
    lookup = labels_by_id()
    joined: list[dict] = []
    for row in requests():
        if row["split"] != split:
            continue
        label = lookup.get(row["request_id"])
        if label is None:
            continue
        joined.append({**row, "route": label["route"]})
    return joined


# ---------------------------------------------------------------------------
# 04_Memory
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def events() -> list[dict]:
    return _read_jsonl(paths.EVENTS)


def events_for(employee_id: str, tenant: str | None = None) -> list[dict]:
    rows = [event for event in events() if event["employee_id"] == employee_id]
    if tenant is not None:
        rows = [event for event in rows if event["tenant"] == tenant]
    return rows


# ---------------------------------------------------------------------------
# 05_Tools
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def model_responses() -> list[dict]:
    return _read_jsonl(paths.MODEL_RESPONSES)


@lru_cache(maxsize=1)
def error_schedule() -> list[dict]:
    return _read_jsonl(paths.ERROR_SCHEDULE)


# ---------------------------------------------------------------------------
# 06_Security
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def redteam() -> list[dict]:
    return _read_jsonl(paths.REDTEAM)


def redteam_attacks() -> list[dict]:
    return [row for row in redteam() if row.get("malicious")]


def redteam_benign() -> list[dict]:
    return [row for row in redteam() if not row.get("malicious")]


# `family` carries a "benign" bucket alongside the attack families, so grouping
# the whole file yields 11 keys. The assignment asks for the ten *attack*
# families (10 x 12 = 120); benign texts are the negative class.
BENIGN_FAMILY = "benign"


def redteam_families() -> dict[str, list[dict]]:
    """The ten attack families, keyed by name. Excludes the `benign` bucket."""
    grouped: dict[str, list[dict]] = {}
    for row in redteam():
        if row["family"] == BENIGN_FAMILY:
            continue
        grouped.setdefault(row["family"], []).append(row)
    return grouped


# ---------------------------------------------------------------------------
# 07_Evaluation
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def runs() -> list[dict]:
    rows = _read_csv(paths.RUNS)
    for row in rows:
        row["success"] = str(row["success"]).strip().lower() == "true"
        row["policy_violation"] = str(row["policy_violation"]).strip().lower() == "true"
        row["human_edit"] = str(row["human_edit"]).strip().lower() == "true"
        for key in ("tool_calls", "correct_calls", "input_tokens",
                    "output_tokens", "duration_ms"):
            row[key] = int(row[key])
    return rows


@lru_cache(maxsize=1)
def spans() -> list[dict]:
    rows = _read_csv(paths.SPANS)
    for row in rows:
        row["start_ms"] = int(row["start_ms"])
        row["end_ms"] = int(row["end_ms"])
        row["duration_ms"] = row["end_ms"] - row["start_ms"]
    return rows


@lru_cache(maxsize=1)
def prices() -> list[dict]:
    rows = _read_csv(paths.PRICES)
    for row in rows:
        row["input_usd_per_million"] = float(row["input_usd_per_million"])
        row["output_usd_per_million"] = float(row["output_usd_per_million"])
    return rows


@lru_cache(maxsize=1)
def audit_groups() -> list[dict]:
    return _read_csv(paths.AUDIT_GROUPS)


@lru_cache(maxsize=1)
def audit_group_by_employee() -> dict[str, str]:
    return {row["employee_id"]: row["audit_group"] for row in audit_groups()}


# ---------------------------------------------------------------------------
# 08_Rollout
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def traffic() -> list[dict]:
    rows = _read_csv(paths.TRAFFIC)
    for row in rows:
        row["received_ms"] = int(row["received_ms"])
        row["load"] = int(row["load"])
        row["feature_enabled"] = str(row["feature_enabled"]).strip().lower() == "true"
    return rows


@lru_cache(maxsize=1)
def manifest() -> list[dict]:
    return json.loads(paths.MANIFEST.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def question_bank() -> dict:
    """The enriched 144-question bank built by scripts/build_question_bank.py."""
    return json.loads(
        (paths.GENERATED / "question_bank.json").read_text(encoding="utf-8")
    )


__all__ = [
    "people", "people_by_id", "department_context", "policy_by_scope",
    "documents", "budget_parts",
    "requests", "labels", "labels_by_id", "requests_by_split", "labelled_requests",
    "events", "events_for",
    "model_responses", "error_schedule",
    "redteam", "redteam_attacks", "redteam_benign", "redteam_families",
    "BENIGN_FAMILY",
    "runs", "spans", "prices", "audit_groups", "audit_group_by_employee",
    "traffic", "manifest", "question_bank",
]
