"""Final API: SQLite-backed cases/sessions plus the LangGraph answer endpoint.

This is the integration layer. It adds no new business rules — it wires the existing adapter, graph,
cache and error envelope together so the four negative paths and the idempotent session creation can
be exercised through `fastapi.testclient.TestClient`.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Literal

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from work.sec05_api_client.errors import ApiError, correlation_id, envelope, install_error_handlers

MAX_PAGE_LIMIT = 5
DEFAULT_PAGE_LIMIT = 2


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(ge=1, le=10)
    method: Literal["lexical", "dense", "hybrid"]


class AnswerRequest(BaseModel):
    """`extra="forbid"` turns an unexpected field into 422 rather than silently ignoring it."""
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=3, max_length=32)
    query: str = Field(min_length=3, max_length=1000)
    mode: Literal["general", "rag", "both"] = "rag"


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=3, max_length=32)


def build_app(*, con, adapter, graph, runner, principal_for) -> FastAPI:
    app = FastAPI(title="Day3 final API", version="1.0.0")
    install_error_handlers(app)

    def current_user(x_user_id: str | None = Header(default=None, alias="X-User-ID")) -> dict:
        if not x_user_id:
            raise ApiError(401, "Missing X-User-ID header.")
        user = adapter.user(x_user_id)
        if user is None:
            raise ApiError(401, f"Unknown X-User-ID '{x_user_id}'.")
        return user

    def _may_read(user: dict, case: dict) -> bool:
        return user["role"] == "admin" or case["owner_id"] == user["user_id"]

    @app.get("/api/health")
    def health() -> dict:
        users = con.execute("SELECT count(*) FROM users").fetchone()[0]
        cases = con.execute("SELECT count(*) FROM cases").fetchone()[0]
        chunks = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
        return {"status": "ok", "engine": "sqlite", "users": users, "cases": cases,
                "chunks": chunks, "synthetic": True}

    @app.get("/api/cases")
    def list_cases(limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1),
                   cursor: str | None = Query(default=None),
                   user: dict = Depends(current_user)) -> dict:
        effective = min(limit, MAX_PAGE_LIMIT)
        rows = con.execute(
            "SELECT case_id, owner_id, topic, summary FROM cases ORDER BY case_id").fetchall()
        rows = [dict(r) for r in rows]
        if user["role"] != "admin":
            rows = [r for r in rows if r["owner_id"] == user["user_id"]]
        if cursor:
            known = con.execute("SELECT 1 FROM cases WHERE case_id=?", (cursor,)).fetchone()
            if known is None:
                raise ApiError(422, f"Unknown cursor '{cursor}'.")
            rows = [r for r in rows if r["case_id"] > cursor]
        page = rows[:effective]
        return {"items": page, "limit_applied": effective,
                "next_cursor": page[-1]["case_id"] if len(page) == effective and len(rows) > effective else None}

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, user: dict = Depends(current_user)) -> dict:
        row = con.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise ApiError(404, f"Case '{case_id}' does not exist.")
        case = dict(row)
        if not _may_read(user, case):
            raise ApiError(403, "You are not allowed to read this case.")
        return case

    @app.post("/api/search")
    def search(payload: SearchRequest, user: dict = Depends(current_user)) -> dict:
        return {"query": payload.query, "top_k": payload.top_k, "method": payload.method,
                "user_id": user["user_id"], "hits": [], "synthetic": True}

    @app.post("/api/sessions")
    def create_session(payload: SessionRequest, response: Response,
                       idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                       user: dict = Depends(current_user)) -> dict:
        row = con.execute("SELECT * FROM cases WHERE case_id=?", (payload.case_id,)).fetchone()
        if row is None:
            raise ApiError(404, f"Case '{payload.case_id}' does not exist.")
        if not _may_read(user, dict(row)):
            raise ApiError(403, "You are not allowed to open a session for this case.")

        fingerprint = json.dumps({"case_id": payload.case_id, "owner_id": user["user_id"]}, sort_keys=True)
        if idempotency_key:
            seen = con.execute(
                "SELECT session_id, owner_id, case_id FROM sessions WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if seen is not None:
                seen_body = json.dumps({"case_id": seen["case_id"], "owner_id": seen["owner_id"]},
                                       sort_keys=True)
                if seen_body != fingerprint:
                    raise ApiError(409, "This Idempotency-Key was already used with a different request body.")
                response.status_code = 200
                return {"session_id": seen["session_id"], "replayed": True, "case_id": payload.case_id}

        session_id = f"S-{uuid.uuid4().hex[:10]}"
        with con:
            con.execute(
                "INSERT INTO sessions (session_id, owner_id, case_id, idempotency_key) VALUES (?,?,?,?)",
                (session_id, user["user_id"], payload.case_id, idempotency_key),
            )
        response.status_code = 201
        return {"session_id": session_id, "replayed": False, "case_id": payload.case_id}

    @app.post("/api/answer")
    def answer(payload: AnswerRequest, request: Request, user: dict = Depends(current_user)) -> dict:
        """Identity and ownership are enforced here, then the graph does its own authorize again."""
        row = con.execute("SELECT * FROM cases WHERE case_id=?", (payload.case_id,)).fetchone()
        if row is None:
            raise ApiError(404, f"Case '{payload.case_id}' does not exist.")
        if not _may_read(user, dict(row)):
            raise ApiError(403, "You are not allowed to read this case.")

        state = runner(graph, query=payload.query, user_id=user["user_id"],
                       case_id=payload.case_id, mode=payload.mode)
        claims = state.answer.get("claims", []) if state.answer else []
        return {
            "status": state.answer.get("status") if state.answer else "error",
            "trace_id": state.correlation_id,
            "route": state.route,
            "claims": claims,
            "limitations": state.answer.get("limitations", []) if state.answer else [],
            "validation": {k: v for k, v in (state.validation or {}).items() if k != "reasons"},
            "abstained": bool(state.answer.get("abstained")) if state.answer else True,
        }

    @app.get("/api/trace/{trace_id}")
    def read_trace(trace_id: str, user: dict = Depends(current_user)) -> dict:
        events = con.execute(
            "SELECT event_id, event_type, latency_ms, status FROM events WHERE correlation_id=? "
            "ORDER BY event_id", (trace_id,)).fetchall()
        return {"trace_id": trace_id, "events": [dict(e) for e in events],
                "count": len(events)}

    return app


# ----------------------------------------------------------------------------- html view
# Built from code points so no editor step can silently decode the entities.
_ESCAPES = {
    "&": "&" + "amp;",
    "<": "&" + "lt;",
    ">": "&" + "gt;",
    '"': "&" + "quot;",
    "'": "&" + "#x27;",
}


def escape_html(text: str) -> str:
    """Escape before interpolation; the browser must never parse answer text as markup."""
    return "".join(_ESCAPES.get(ch, ch) for ch in str(text))


def render_answer_page(answer: dict, sources: list[dict]) -> str:
    """Minimal RTL view. Answer text goes through `textContent`, never `innerHTML`."""
    claims_html = "".join(
        f'<li><span class="claim">{escape_html(c["text"])}</span> '
        f'<span class="cite">[{escape_html(", ".join(c.get("citation_ids", [])))}]</span></li>'
        for c in answer.get("claims", [])
    ) or "<li class=\"muted\">پاسخی تولید نشد.</li>"

    sources_html = "".join(
        f'<li>{escape_html(s.get("doc_id", ""))} — {escape_html(s.get("section") or "")} '
        f'<code>{escape_html(s.get("chunk_id", ""))}</code></li>'
        for s in sources
    ) or "<li class=\"muted\">منبعی بازیابی نشد.</li>"

    # Escape `<` inside the JSON block as well: a literal "</script>" would close the tag early,
    # and even a harmless "<script>" string has no business appearing unescaped in the document.
    payload = (json.dumps({"claims": answer.get("claims", [])}, ensure_ascii=False)
               .replace("<", "\\u003c").replace(">", "\\u003e"))

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>پاسخ مستند — Day 3</title>
<style>
  body {{ font-family: Tahoma, system-ui, sans-serif; max-width: 46rem; margin: 2rem auto; line-height: 1.9; }}
  .claim {{ font-weight: 600; }}
  .cite {{ color: #4b5563; font-size: .85em; }}
  .muted {{ color: #9ca3af; }}
  ul {{ padding-inline-start: 1.4rem; }}
  code {{ background: #f3f4f6; padding: .1rem .35rem; border-radius: 4px; direction: ltr; display: inline-block; }}
</style>
</head>
<body>
  <h1>پاسخ مستند</h1>
  <p>وضعیت: <strong>{escape_html(answer.get("status", "unknown"))}</strong> — مسیر:
     <strong>{escape_html(answer.get("route") or "-")}</strong></p>

  <h2>ادعاها</h2>
  <ul id="claims">{claims_html}</ul>

  <h2>منابع</h2>
  <ul>{sources_html}</ul>

  <p class="muted">دادهٔ مصنوعی · پاسخ استخراجی از شواهد بازیابی‌شده · هیچ LLM پولی فراخوانی نشده</p>

  <script id="answer-data" type="application/json">{payload}</script>
  <script>
    // Answer text is inserted with textContent so a payload like "<script>" is displayed, not executed.
    const data = JSON.parse(document.getElementById("answer-data").textContent);
    const list = document.getElementById("claims");
    if (data.claims && data.claims.length) {{
      list.replaceChildren();
      for (const claim of data.claims) {{
        const li = document.createElement("li");
        const span = document.createElement("span");
        span.className = "claim";
        span.textContent = claim.text;
        li.appendChild(span);
        list.appendChild(li);
      }}
    }}
  </script>
</body>
</html>
"""
