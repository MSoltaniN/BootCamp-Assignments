"""Local FastAPI app used only as a teaching fixture for section 5.

Identity comes from the `X-User-ID` header and the users/cases are the synthetic rows in
`datasets/03_Application`. This is NOT real authentication and NOT a real service; it exists so the
client contract (error envelope, pagination, idempotency, validation) can be exercised with
`fastapi.testclient.TestClient` without a network.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .errors import ApiError, install_error_handlers

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "datasets" / "03_Application"

MAX_PAGE_LIMIT = 5          # backend cap; a larger client request is clamped, never honoured blindly
DEFAULT_PAGE_LIMIT = 2

app = FastAPI(title="Day3 section 5 fixture API", version="1.0.0")
install_error_handlers(app)


# ----------------------------------------------------------------------------- fixtures
def _load_cases() -> list[dict]:
    rows = []
    with (DATA / "cases.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return sorted(rows, key=lambda r: r["case_id"])          # stable total order


def _load_users() -> dict[str, dict]:
    import csv

    with (DATA / "users.csv").open(encoding="utf-8", newline="") as fh:
        return {row["user_id"]: row for row in csv.DictReader(fh)}


CASES = _load_cases()
USERS = _load_users()
CASES_BY_ID = {c["case_id"]: c for c in CASES}

# session store: idempotency_key -> {"session_id":..., "fingerprint":...}
SESSIONS: dict[str, dict] = {}
SESSIONS_BY_ID: dict[str, dict] = {}


# ----------------------------------------------------------------------------- auth (fixture)
def current_user(x_user_id: str | None = Header(default=None, alias="X-User-ID")) -> dict:
    if not x_user_id:
        raise ApiError(401, "Missing X-User-ID header.")
    user = USERS.get(x_user_id)
    if user is None:
        raise ApiError(401, f"Unknown X-User-ID '{x_user_id}'.")
    return user


def _may_read(user: dict, case: dict) -> bool:
    return user["role"] == "admin" or case["owner_id"] == user["user_id"]


# ----------------------------------------------------------------------------- models
class SearchRequest(BaseModel):
    """`extra="forbid"` is what makes an unexpected field a 422 instead of being ignored."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(ge=1, le=10)
    method: Literal["lexical", "dense", "hybrid"]


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=3, max_length=32)


# ----------------------------------------------------------------------------- routes
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "cases": len(CASES), "users": len(USERS), "synthetic": True}


@app.get("/api/cases")
def list_cases(
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1),
    cursor: str | None = Query(default=None),
    user: dict = Depends(current_user),
) -> dict:
    """Cursor pagination over a stable order.

    `limit` is clamped in the backend, and the cursor is the last `case_id` returned, so the same
    request twice yields the same page and a growing list never shifts an in-flight page.
    """
    effective = min(limit, MAX_PAGE_LIMIT)
    rows = CASES
    if user["role"] != "admin":
        rows = [c for c in rows if c["owner_id"] == user["user_id"]]
    if cursor:
        if cursor not in CASES_BY_ID:
            raise ApiError(422, f"Unknown cursor '{cursor}'.")
        rows = [c for c in rows if c["case_id"] > cursor]
    page = rows[:effective]
    return {
        "items": page,
        "limit_requested": limit,
        "limit_applied": effective,
        "next_cursor": page[-1]["case_id"] if len(page) == effective and len(rows) > effective else None,
    }


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, user: dict = Depends(current_user)) -> dict:
    case = CASES_BY_ID.get(case_id)
    if case is None:
        raise ApiError(404, f"Case '{case_id}' does not exist.")
    if not _may_read(user, case):
        # Deliberately does not echo summary/topic: a 403 must not leak private case text.
        raise ApiError(403, "You are not allowed to read this case.")
    return case


@app.post("/api/search")
def search(payload: SearchRequest, user: dict = Depends(current_user)) -> dict:
    return {
        "query": payload.query,
        "top_k": payload.top_k,
        "method": payload.method,
        "user_id": user["user_id"],
        "hits": [],
        "synthetic": True,
    }


@app.post("/api/sessions")
def create_session(
    payload: SessionRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict = Depends(current_user),
) -> dict:
    case = CASES_BY_ID.get(payload.case_id)
    if case is None:
        raise ApiError(404, f"Case '{payload.case_id}' does not exist.")
    if not _may_read(user, case):
        raise ApiError(403, "You are not allowed to open a session for this case.")

    fingerprint = json.dumps({"case_id": payload.case_id, "owner_id": user["user_id"]}, sort_keys=True)
    if idempotency_key:
        seen = SESSIONS.get(idempotency_key)
        if seen is not None:
            if seen["fingerprint"] != fingerprint:
                raise ApiError(409, "This Idempotency-Key was already used with a different request body.")
            response.status_code = 200
            return {"session_id": seen["session_id"], "replayed": True, "case_id": payload.case_id}
    session_id = f"S-{uuid.uuid4().hex[:10]}"
    if idempotency_key:
        SESSIONS[idempotency_key] = {"session_id": session_id, "fingerprint": fingerprint}
    SESSIONS_BY_ID[session_id] = {"session_id": session_id, "owner_id": user["user_id"], "case_id": payload.case_id}
    response.status_code = 201
    return {"session_id": session_id, "replayed": False, "case_id": payload.case_id}


@app.get("/api/sessions/{session_id}")
def read_session(session_id: str, user: dict = Depends(current_user)) -> dict:
    session = SESSIONS_BY_ID.get(session_id)
    if session is None:
        raise ApiError(404, f"Session '{session_id}' does not exist.")
    if user["role"] != "admin" and session["owner_id"] != user["user_id"]:
        raise ApiError(403, "You are not allowed to read this session.")
    return session


@app.get("/api/boom")
def boom() -> None:
    """Deliberate failure used to prove the 500 envelope keeps a correlation id."""
    raise RuntimeError("synthetic crash for the error-contract test")
