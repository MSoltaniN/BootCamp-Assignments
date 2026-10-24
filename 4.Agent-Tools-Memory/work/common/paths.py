"""Canonical project paths.

Every script and notebook cell imports this module instead of hard-coding
relative paths, so the same code runs from the repo root, from `work/`, or from
inside a notebook kernel.
"""

from __future__ import annotations

from pathlib import Path

# work/common/paths.py -> work/ -> project root
ROOT = Path(__file__).resolve().parents[2]

# student pack, extracted
PACK = ROOT / "assignment" / "source" / "Day4"
DATA = PACK / "Day4_Datasets"
GRADING = PACK / "Day4_Grading"
STARTER = PACK / "Day4_Starter"

# datasets, grouped the way the assignment refers to them
HR = DATA / "01_HR"
CONTEXT = DATA / "02_Context"
REQUESTS = DATA / "03_Requests"
MEMORY = DATA / "04_Memory"
TOOLS = DATA / "05_Tools"
SECURITY = DATA / "06_Security"
EVALUATION = DATA / "07_Evaluation"
ROLLOUT = DATA / "08_Rollout"

# concrete files
PEOPLE = HR / "people.jsonl"
DEPARTMENT_CONTEXT = HR / "department_context.jsonl"
DOCUMENTS = CONTEXT / "documents.jsonl"
BUDGET_PARTS = CONTEXT / "budget_parts.csv"
REQUESTS_FILE = REQUESTS / "requests.jsonl"
LABELS = REQUESTS / "labels_train_dev.jsonl"
EVENTS = MEMORY / "events.jsonl"
MODEL_RESPONSES = TOOLS / "model_responses.jsonl"
ERROR_SCHEDULE = TOOLS / "error_schedule.jsonl"
REDTEAM = SECURITY / "redteam.jsonl"
RUNS = EVALUATION / "runs.csv"
SPANS = EVALUATION / "spans.csv"
PRICES = EVALUATION / "prices.csv"
AUDIT_GROUPS = EVALUATION / "audit_groups.csv"
TRAFFIC = ROLLOUT / "traffic.csv"
MANIFEST = DATA / "manifest.json"
QUESTION_SCHEMA = GRADING / "question_schema.json"
CHECKER = GRADING / "check_submission.py"

# our own code and outputs
CODE = ROOT / "Day4_Code"
OUTPUT = ROOT / "Day4_Run_Output"
WORK = ROOT / "work"
DOCS = ROOT / "docs"
GENERATED = DOCS / "generated"
DELIVERABLES = ROOT / "deliverables"

# databases and reports we produce
APPLICATION_DB = OUTPUT / "application.sqlite"
CHECKPOINTS_DB = OUTPUT / "checkpoints.sqlite"
DATABASE_CHECK = OUTPUT / "database_check.json"
AGENT_TRACE = OUTPUT / "agent_trace.json"
ROUTER_CONFIG = OUTPUT / "locked_router_config.json"
ROUTE_PREDICTIONS = OUTPUT / "route_predictions.jsonl"
TRACES = OUTPUT / "traces"


def ensure_output_dirs() -> None:
    """Create the output folders so writers never fail on a missing parent."""
    for folder in (OUTPUT, CODE, TRACES, DELIVERABLES):
        folder.mkdir(parents=True, exist_ok=True)


__all__ = [
    "ROOT", "PACK", "DATA", "GRADING", "STARTER",
    "HR", "CONTEXT", "REQUESTS", "MEMORY", "TOOLS", "SECURITY",
    "EVALUATION", "ROLLOUT",
    "PEOPLE", "DEPARTMENT_CONTEXT", "DOCUMENTS", "BUDGET_PARTS",
    "REQUESTS_FILE", "LABELS", "EVENTS", "MODEL_RESPONSES", "ERROR_SCHEDULE",
    "REDTEAM", "RUNS", "SPANS", "PRICES", "AUDIT_GROUPS", "TRAFFIC",
    "MANIFEST", "QUESTION_SCHEMA", "CHECKER",
    "CODE", "OUTPUT", "WORK", "DOCS", "GENERATED", "DELIVERABLES",
    "APPLICATION_DB", "CHECKPOINTS_DB", "DATABASE_CHECK", "AGENT_TRACE",
    "ROUTER_CONFIG", "ROUTE_PREDICTIONS", "TRACES",
    "ensure_output_dirs",
]
