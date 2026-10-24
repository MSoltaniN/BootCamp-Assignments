"""LangGraph memory graph with durable SQLite checkpoints and human approval.

The graph has three nodes:

    prepare  -> writes a draft profile payload into state
    approval -> interrupt(); nothing is written until a reviewer resumes
    commit   -> writes the profile + audit inside a single transaction

The same `thread_id` resumes across a *new* process, which is what proves the
checkpoint is durable rather than living in RAM.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "Day4_Code"))

from store import Store  # noqa: E402

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt
except ImportError as error:  # pragma: no cover
    raise SystemExit(f"langgraph is required: {error}") from error


class MemoryState(TypedDict, total=False):
    tenant: str
    employee_id: str
    payload: dict
    approval_id: str
    reviewer: str
    status: str
    version: int


def build_graph(store: Store, checkpoint_path: str | Path):
    """Compile the graph against a durable SqliteSaver."""

    def prepare(state: MemoryState) -> MemoryState:
        return {**state, "status": "pending_approval"}

    def approval(state: MemoryState) -> MemoryState:
        # Blocks here until a caller resumes the thread with a decision.
        decision = interrupt(
            {
                "question": "Approve writing this profile?",
                "employee_id": state.get("employee_id"),
                "payload": state.get("payload", {}),
            }
        )
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else False
        reviewer = (decision or {}).get("reviewer", "unknown") if isinstance(decision, dict) else "unknown"
        return {
            **state,
            "status": "approved" if approved else "rejected",
            "reviewer": reviewer,
        }

    def commit(state: MemoryState) -> MemoryState:
        if state.get("status") != "approved":
            return state

        tenant = state["tenant"]
        employee_id = state["employee_id"]
        payload = state["payload"]
        approval_id = state["approval_id"]

        base = store.current_version(tenant, employee_id)
        store.add_approval(
            approval_id=approval_id, tenant=tenant, employee_id=employee_id,
            payload=payload, base_version=base, reviewer=state.get("reviewer", "reviewer"),
            approved=True,
        )
        result = store.write_profile(
            idempotency_key=f"idem-{approval_id}", tenant=tenant,
            employee_id=employee_id, payload=payload, version=base + 1,
            approval_id=approval_id,
        )
        return {**state, "version": result["version"]}

    builder = StateGraph(MemoryState)
    builder.add_node("prepare", prepare)
    builder.add_node("approval", approval)
    builder.add_node("commit", commit)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "approval")
    builder.add_edge("approval", "commit")
    builder.add_edge("commit", END)

    conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    return builder.compile(checkpointer=saver)


def checkpoint_schema(path: str | Path) -> dict:
    """Describe the SqliteSaver table so the report can cite it."""
    conn = sqlite3.connect(str(path))
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        columns: dict[str, list[str]] = {}
        for table in tables:
            columns[table] = [
                row[1] for row in conn.execute(f"PRAGMA table_info({table})")
            ]
        rows = 0
        if "checkpoints" in tables:
            rows = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
        return {"tables": tables, "columns": columns, "checkpoint_rows": rows}
    finally:
        conn.close()


__all__ = ["build_graph", "checkpoint_schema", "MemoryState"]
