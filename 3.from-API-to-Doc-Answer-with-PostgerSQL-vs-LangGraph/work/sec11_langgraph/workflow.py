"""The LangGraph workflow: authorization, routing, tools, extractive answer, citation validation.

Design decisions that the sub-questions test:

* Authorization runs **before** any tool. A denied request leaves no evidence and no history in
  state, so a later node cannot accidentally expose them.
* Document text and tool output enter as **data**. The classifier and generator never interpret
  them as commands; nothing in the workflow can be steered by text inside a document.
* The reference generator is deterministic and extractive: it copies a real sentence and cites the
  chunk it came from. It cannot invent, which is why `general` mode must abstain.
* Validation is two-stage: structural (does the id exist, does the quote appear) and semantic
  (does the claim equal the quote). The gap between the two is the point of 11.7.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Literal

ROUTES = ("history", "research", "both", "clarify", "unsupported")
MODES = ("general", "rag", "both")


# ----------------------------------------------------------------------------- state
@dataclass
class WorkflowState:
    """Per-request state. No secret ever lives here, and it is never shared between requests."""

    query: str
    user_id: str
    case_id: str
    mode: str = "rag"
    correlation_id: str = field(default_factory=lambda: f"TRACE-{uuid.uuid4().hex[:12]}")

    route: str | None = None
    route_reason: str = ""
    denied: bool = False
    deny_reason: str = ""

    evidence: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    answer: dict | None = None
    validation: dict | None = None
    trace: list[dict] = field(default_factory=list)

    forbidden_keys: tuple = ("secret", "api_key", "token", "password", "authorization")

    def add_trace(self, node: str, detail: str, **extra) -> None:
        self.trace.append({"seq": len(self.trace) + 1, "node": node, "detail": detail,
                           "correlation_id": self.correlation_id, **extra})

    def secrets_present(self) -> list[str]:
        """Scan the whole state for keys that must never be there."""
        found: list[str] = []

        def walk(value, path="state"):
            if isinstance(value, dict):
                for key, item in value.items():
                    if any(bad in key.lower() for bad in self.forbidden_keys):
                        found.append(f"{path}.{key}")
                    walk(item, f"{path}.{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    walk(item, f"{path}[{i}]")

        walk(self.__dict__)
        return found


# ----------------------------------------------------------------------------- authorization
def authorize(state: WorkflowState, adapter) -> WorkflowState:
    """Ownership is checked against the database before any tool can run."""
    status, case = adapter.read_case(state.user_id, state.case_id)
    if status != 200:
        state.denied = True
        state.deny_reason = {401: "unauthenticated", 403: "not_owner", 404: "case_not_found"}.get(status, "denied")
        state.evidence = []
        state.history = []
        state.add_trace("authorize", f"denied:{state.deny_reason}", status=status)
        return state
    state.add_trace("authorize", "allowed", status=status, owner=case["owner_id"])
    return state


# ----------------------------------------------------------------------------- routing
_INJECTION = re.compile(
    r"ignore (all |any |the |your )?(previous|prior|above) (instructions|rules)|"
    r"disregard (the |your )?(system|rules)|reveal (the |your )?(api key|secret|password)|"
    r"\byou are now\b|\bsystem:\s|\boverride\b.*\b(policy|access|rules)\b|"
    r"\bbypass\b|\bdelete\b.*\brecords?\b|\ball tenants?\b|\bexfiltrate\b|"
    r"call the .*tool\b.*\bsend\b|upload .*secret", re.I)
_HISTORY = re.compile(r"\bcase\b|\bhistory\b|\btimeline\b|\bnotes\b|\brecord\b|\bprogress\b", re.I)
_RESEARCH = re.compile(r"\bpep\b|\bdocuments?\b|\bevidence\b|\bspecification\b|\bresearch\b|"
                       r"\bsources?\b|\bpublic\b|\bpassage\b|\bguideline\b", re.I)
_VAGUE = re.compile(r"^\s*(help|what|why|how|tell me more|\?)\s*$", re.I)


def route_query(state: WorkflowState) -> WorkflowState:
    """Map the question to a tool set, with an explicit fallback.

    `clarify` and `unsupported` are answered without any private lookup, so a malicious or
    ambiguous request cannot be used to probe the corpus.
    """
    query = state.query.strip()
    if _INJECTION.search(query):
        state.route, state.route_reason = "unsupported", "instruction_override_attempt"
    elif len(query.split()) < 2 or _VAGUE.match(query):
        state.route, state.route_reason = "clarify", "too_vague"
    else:
        has_history = bool(_HISTORY.search(query))
        has_research = bool(_RESEARCH.search(query))
        if has_history and has_research:
            state.route, state.route_reason = "both", "case_and_source_cues"
        elif has_history:
            state.route, state.route_reason = "history", "case_cue"
        elif has_research:
            state.route, state.route_reason = "research", "source_cue"
        else:
            state.route, state.route_reason = "clarify", "no_tool_cue"
    state.add_trace("route", f"{state.route}:{state.route_reason}")
    return state


# ----------------------------------------------------------------------------- tools
def history_tool(state: WorkflowState, con) -> WorkflowState:
    """Parameterised query plus an owner predicate in the SQL itself.

    The owner check is repeated here rather than trusted from the caller: if authorization were
    ever bypassed upstream, this tool still cannot return another user's rows.
    """
    rows = con.execute(
        """
        SELECT m.message_id, m.content, m.role
        FROM messages m
        JOIN sessions s ON s.session_id = m.session_id
        WHERE s.owner_id = ? AND s.case_id = ?
        ORDER BY m.message_id
        """,
        (state.user_id, state.case_id),
    ).fetchall()
    state.history = [{"message_id": r["message_id"], "content": r["content"], "role": r["role"]}
                     for r in rows]
    state.add_trace("history_tool", f"rows:{len(state.history)}")
    return state


def research_tool(state: WorkflowState, retriever, principal) -> WorkflowState:
    """Public evidence plus the caller's own tenant, filtered before ranking."""
    hits = retriever(state.query, principal, top_k=5)
    state.evidence = hits
    state.add_trace("research_tool", f"hits:{len(hits)}",
                    chunks=[h["chunk_id"] for h in hits])
    return state


# ----------------------------------------------------------------------------- generation
def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def generate(state: WorkflowState) -> WorkflowState:
    """Deterministic extractive answer.

    The generator copies one real sentence from the best evidence chunk. It has no freedom to
    paraphrase, so it cannot invent a fact or a citation — and by consequence it cannot answer at
    all in `general` mode, which is exactly what 11.5 requires it to admit.
    """
    if state.denied:
        state.answer = {"status": "denied", "mode": state.mode, "claims": [],
                        "limitations": [f"request denied: {state.deny_reason}"], "abstained": True}
        state.add_trace("generate", "denied_no_answer")
        return state

    if state.route == "clarify":
        state.answer = {"status": "clarify", "mode": state.mode, "claims": [],
                        "limitations": ["question is too vague to choose a tool"], "abstained": True}
        state.add_trace("generate", "clarify")
        return state

    if state.route == "unsupported":
        state.answer = {"status": "unsupported", "mode": state.mode, "claims": [],
                        "limitations": ["request asks for something the workflow does not do"],
                        "abstained": True}
        state.add_trace("generate", "unsupported")
        return state

    claims: list[dict] = []
    limitations: list[str] = []

    if state.mode == "general":
        # The extractive baseline has no independent knowledge, so it must abstain rather than guess.
        state.answer = {"status": "abstained", "mode": "general", "claims": [],
                        "limitations": ["general mode needs free generation, which this baseline "
                                        "does not do; no evidence was retrieved"], "abstained": True}
        state.add_trace("generate", "general_abstained")
        return state

    if state.route in ("research", "both") and state.evidence:
        for hit in state.evidence:
            for sentence in _sentences(hit["content"]):
                if _overlaps(sentence, state.query):
                    claims.append({
                        "text": sentence, "citation_ids": [hit["citation_id"]],
                        "quote": sentence, "source": hit["doc_id"],
                    })
                    break
            if len(claims) >= 3:
                break

    if state.route in ("history", "both") and state.history:
        latest = state.history[-1]
        claims.append({
            "text": f"The latest recorded case note says: {latest['content']}",
            "citation_ids": ["F-" + latest["message_id"]], "quote": latest["content"],
            "source": "case_history",
        })

    if not claims:
        limitations.append("no retrieved passage matched the question")

    state.answer = {"status": "answered" if claims else "no_evidence", "mode": state.mode,
                    "claims": claims, "limitations": limitations, "abstained": not claims}
    state.add_trace("generate", f"claims:{len(claims)}", mode=state.mode)
    return state


_STOPWORDS = {"the", "a", "an", "is", "are", "what", "which", "how", "does", "do", "for", "of",
              "to", "in", "on", "and", "or", "it", "this", "that", "with", "be", "should"}


def _overlaps(sentence: str, query: str) -> bool:
    words = {w for w in re.findall(r"[a-z0-9]+", sentence.lower()) if w not in _STOPWORDS and len(w) > 2}
    asked = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in _STOPWORDS and len(w) > 2}
    return bool(words & asked)


# ----------------------------------------------------------------------------- validation
def validate_structural(answer: dict, valid_citation_ids: set[str], evidence_text: dict[str, str]) -> dict:
    """Structural checks only: does the id exist, and does the quote appear in its source?

    This is deliberately *not* enough. A claim can cite a real chunk, quote it verbatim, and still
    assert something the quote does not support. That gap is what 11.7 exposes.
    """
    if answer is None:
        return {"accepted": 0, "rejected": 0, "reasons": []}

    accepted, rejected, reasons = 0, 0, []
    for claim in answer.get("claims", []):
        problem = None
        if not claim["citation_ids"]:
            problem = "missing_citation"
        else:
            unknown = [c for c in claim["citation_ids"] if c not in valid_citation_ids]
            if unknown:
                problem = f"unknown_citation:{','.join(unknown)}"
            elif claim["quote"] and claim["quote"] not in evidence_text.get(claim["citation_ids"][0], ""):
                problem = "quote_not_in_source"
        if problem:
            rejected += 1
            reasons.append({"claim": claim["text"], "reason": problem})
        else:
            accepted += 1
    return {"accepted": accepted, "rejected": rejected, "reasons": reasons}


def validate_extractive(answer: dict, valid_citation_ids: set[str],
                        evidence_text: dict[str, str]) -> dict:
    """Structural checks **plus** claim == quote.

    The extractive baseline may only repeat what the source says, so any difference between the
    claim and its own quote is a fabrication and is rejected even when the citation id is real.
    """
    structural = validate_structural(answer, valid_citation_ids, evidence_text)
    accepted, rejected = 0, 0
    reasons = list(structural["reasons"])
    for claim in (answer or {}).get("claims", []):
        already_rejected = any(r["claim"] == claim["text"] for r in structural["reasons"])
        if already_rejected:
            # Counted as rejected by the structural pass; keep the total equal to the claim count.
            rejected += 1
            continue
        if claim["text"].strip() != claim["quote"].strip():
            rejected += 1
            reasons.append({"claim": claim["text"], "reason": "claim_not_equal_to_quote"})
        else:
            accepted += 1
    return {"accepted": accepted, "rejected": rejected, "reasons": reasons,
            "structural_only": structural}


def validate_node(state: WorkflowState, evidence_text: dict[str, str], extractive: bool = True) -> WorkflowState:
    valid = {hit["citation_id"] for hit in state.evidence}
    valid |= {"F-" + row["message_id"] for row in state.history}
    checker = validate_extractive if extractive else validate_structural
    state.validation = checker(state.answer, valid, evidence_text)
    state.add_trace("validate", f"accepted:{state.validation['accepted']} "
                                f"rejected:{state.validation['rejected']}")
    return state


# ----------------------------------------------------------------------------- cache
def cache_report(user_id: str, tenant: str, model_id: str, corpus_version: str, prompt_version: str,
                 **extra) -> str:
    """Cache identity must include everything that changes the answer.

    Omitting user, tenant, model, corpus, or prompt version means one caller can be served an answer
    built from another caller's permissions or a different corpus snapshot.
    """
    import hashlib
    import json

    payload = {"user_id": user_id, "tenant": tenant, "model_id": model_id,
               "corpus_version": corpus_version, "prompt_version": prompt_version, **extra}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------------- telemetry
_SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "token", "access_token", "refresh_token",
                   "password", "secret", "client_secret", "cookie"}


def sanitise(value):
    if isinstance(value, dict):
        return {k: sanitise(v) for k, v in value.items() if k.lower() not in _SENSITIVE_KEYS}
    if isinstance(value, list):
        return [sanitise(v) for v in value]
    if isinstance(value, str) and "TEST-ONLY-SECRET" in value:
        return "[REDACTED]"
    return value


def emit_events(state: WorkflowState) -> list[dict]:
    """One minimal event per node, sharing the correlation id and carrying no private text."""
    events = []
    for step in state.trace:
        events.append(sanitise({
            "correlation_id": state.correlation_id,
            "seq": step["seq"],
            "node": step["node"],
            "detail": step["detail"],
            "user_id": state.user_id,
            "route": state.route,
            "metadata": {"mode": state.mode, "case_id": state.case_id},
        }))
    return events
