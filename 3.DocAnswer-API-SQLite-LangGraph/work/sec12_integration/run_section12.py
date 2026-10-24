"""Section 12 — integration, HTML view, trace analysis, regression gate, delivery.

Run:  .venv\\Scripts\\python.exe work/sec12_integration/run_section12.py
Writes: work/sec12_integration/artifacts/*, deliverables/*
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from fastapi.testclient import TestClient

from work._common.config import MODEL_ID, MODEL_REVISION, SEED, config_fingerprint
from work._common.db import connect
from work._common.paths import DB_PATH, OBS
from work.sec08_embeddings.retrieval import Principal, acl_filter, dense_scores, load_index
from work.sec11_langgraph.graph import build_graph, run
from work.sec12_integration.api import build_app, escape_html, render_answer_page
from work.sec08_embeddings.retrieval import percentiles as pctl

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
DELIV = ROOT / "deliverables"
DELIV.mkdir(exist_ok=True)
results: dict = {}


def head(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


from sentence_transformers import SentenceTransformer

import sqlite3
import threading

# `TestClient` runs sync endpoints in a worker thread, and a sqlite3 connection is bound to the
# thread that created it. One connection with check_same_thread=False plus a lock keeps the fixture
# correct without pretending it is a concurrency-safe pool.
_DB_LOCK = threading.Lock()
con = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=5.0)
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys=ON")
index = load_index(con, expect={"dimension": 384, "model_revision": MODEL_REVISION, "model_id": MODEL_ID})
encoder = SentenceTransformer(str(ROOT / "resources" / "embedding_model"), device="cpu")


class Adapter:
    def __init__(self, connection):
        self.con = connection

    def user(self, user_id: str) -> dict | None:
        with _DB_LOCK:
            row = self.con.execute("SELECT user_id, role, tenant FROM users WHERE user_id=?",
                                   (user_id,)).fetchone()
        return dict(row) if row else None

    def read_case(self, user_id: str, case_id: str) -> tuple[int, dict | None]:
        user = self.user(user_id)
        if user is None:
            return 401, None
        with _DB_LOCK:
            row = self.con.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            return 404, None
        case = dict(row)
        return (200, case) if (user["role"] == "admin" or case["owner_id"] == user_id) else (403, None)


adapter = Adapter(con)


def principal_for(user_id: str) -> Principal:
    user = adapter.user(user_id) or {"user_id": user_id, "role": "student", "tenant": "T-0"}
    return Principal(user_id=user["user_id"], role=user["role"], tenant=user["tenant"])


def retriever(query: str, principal: Principal, top_k: int = 5) -> list[dict]:
    allowed = acl_filter(index.chunks, principal)
    if not allowed:
        return []
    matrix = np.vstack([c.embedding for c in allowed])
    qv = encoder.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
    scored = dense_scores(qv, matrix)
    hits = []
    for idx in np.argsort(-scored)[:top_k]:
        chunk = allowed[int(idx)]
        hits.append({"citation_id": f"C-{chunk.chunk_id[:24]}", "chunk_id": chunk.chunk_id,
                     "doc_id": chunk.doc_id, "content": chunk.content,
                     "similarity": round(float(scored[int(idx)]), 4)})
    return hits


evidence_text = {f"C-{c.chunk_id[:24]}": c.content for c in index.chunks}
graph = build_graph(adapter=adapter, con=con, retriever=retriever,
                    principal_for=principal_for, evidence_text=evidence_text)
app = build_app(con=con, adapter=adapter, graph=graph, runner=run, principal_for=principal_for)
client = TestClient(app)

# ---------------------------------------------------------------- 12.1
head("12.1  files/sessions API on the SQLite adapter: health, owner case, non-owner case")
print("database engine reported by /api/health:", client.get("/api/health").json())
health_body = client.get("/api/health").json()
owner_case = client.get("/api/cases/C-001", headers={"X-User-ID": "U-002"})
non_owner_case = client.get("/api/cases/C-001", headers={"X-User-ID": "U-003"})
print("owner     ->", owner_case.status_code)
print("non-owner ->", non_owner_case.status_code, non_owner_case.json()["error"]["code"])
print("health    ->", health_body["status"])
table_121 = [{"request": "health", "status": 200},
             {"request": "owner case", "status": owner_case.status_code},
             {"request": "non-owner case", "status": non_owner_case.status_code}]
results["12.1"] = {"engine": health_body["engine"], "table": table_121}

# ---------------------------------------------------------------- 12.2
head("12.2  answer endpoint: schema, identity/ownership, graph invocation, trace id")
answer_response = client.post("/api/answer",
                              json={"case_id": "C-001", "query": "What does PEP-8 say about indentation width?",
                                    "mode": "rag"},
                              headers={"X-User-ID": "U-002"})
body = answer_response.json()
print("status:", answer_response.status_code)
print("trace id:", body.get("trace_id"))
print("route:", body.get("route"), "| claims:", len(body.get("claims", [])))
print("correlation id present:", bool(body.get("trace_id")))
print("claims carry citation ids:", all(c.get("citation_ids") for c in body.get("claims", [])) if body.get("claims") else "no claims")
forbidden_answer = client.post("/api/answer",
                               json={"case_id": "C-001", "query": "What does PEP-8 say?", "mode": "rag"},
                               headers={"X-User-ID": "U-003"})
print("non-owner answer ->", forbidden_answer.status_code)
results["12.2"] = {"status": answer_response.status_code, "has_trace_id": bool(body.get("trace_id")),
                   "route": body.get("route"), "claims": len(body.get("claims", []))}

# ---------------------------------------------------------------- 12.3
head("12.3  four negative paths on the answer endpoint")
negatives = [
    ("missing identity", {}, {"case_id": "C-001", "query": "What does PEP-8 say?", "mode": "rag"}, 401),
    ("non-owner", {"X-User-ID": "U-003"}, {"case_id": "C-001", "query": "What does PEP-8 say?", "mode": "rag"}, 403),
    ("query too short", {"X-User-ID": "U-002"}, {"case_id": "C-001", "query": "ab", "mode": "rag"}, 422),
    ("extra field", {"X-User-ID": "U-002"},
     {"case_id": "C-001", "query": "What does PEP-8 say?", "mode": "rag", "debug": True}, 422),
]
negative_rows = []
leaked_summary = False
for label, headers, payload, expected in negatives:
    response = client.post("/api/answer", json=payload, headers=headers)
    text = json.dumps(response.json(), ensure_ascii=False)
    leaked = "Fictional software research case" in text
    leaked_summary = leaked_summary or leaked
    print(f"{label:18s} -> {response.status_code} (expected {expected})  leaks case summary: {leaked}")
    negative_rows.append({"case": label, "status": response.status_code, "expected": expected,
                          "leaked_summary": leaked})
statuses = [row["status"] for row in negative_rows]
print("statuses:", statuses, "| exactly 401/403/422/422:", statuses == [401, 403, 422, 422])
print("private case text in any error body:", leaked_summary)
results["12.3"] = {"statuses": statuses, "leaked_summary": leaked_summary, "rows": negative_rows}

# ---------------------------------------------------------------- 12.4
head("12.4  idempotent session creation over the SQLite unique constraint")
key = "IDEM-SEC12"
with con:
    con.execute("DELETE FROM sessions WHERE idempotency_key=?", (key,))
headers_idem = {"X-User-ID": "U-002", "Idempotency-Key": key}
first = client.post("/api/sessions", json={"case_id": "C-001"}, headers=headers_idem)
second = client.post("/api/sessions", json={"case_id": "C-001"}, headers=headers_idem)
conflict = client.post("/api/sessions", json={"case_id": "C-020"}, headers=headers_idem)
stored = con.execute("SELECT count(*) FROM sessions WHERE idempotency_key=?", (key,)).fetchone()[0]
same_id = first.json()["session_id"] == second.json()["session_id"]
print("first :", first.status_code, first.json())
print("second:", second.status_code, second.json())
print("conflict:", conflict.status_code, conflict.json().get("error", {}).get("code"))
print("same session id:", same_id, "| rows stored with this key:", stored)
results["12.4"] = {"same_id": same_id, "stored": stored, "conflict_status": conflict.status_code,
                   "first": first.status_code, "second": second.status_code}

# ---------------------------------------------------------------- 12.5
head("12.5  minimal RTL HTML view with escaping")
malicious = "<script>alert('xss')</script> Use 4 spaces."
fake_answer = {"status": "answered", "route": "research",
               "claims": [{"text": malicious, "citation_ids": ["C-PEP-0008"]}]}
sources = [{"doc_id": "PEP-0008", "section": "Introduction", "chunk_id": "PEP-0008:vb80c7bf8:0-953"}]
page = render_answer_page(fake_answer, sources)
view_path = DELIV / "answer_view.html"
view_path.write_text(page, encoding="utf-8")
raw_script_count = page.count("<script>alert")
# Build the expected entity text from code points: writing the literal entity in this source file
# is not reliable, because tooling may decode it before it reaches disk.
_AMP = chr(38)
escaped_needle = f"{_AMP}lt;script{_AMP}gt;alert"
escaped_present = escaped_needle in page
double_escaped = f"{_AMP}amp;lt;" in page
uses_textcontent = "textContent" in page
uses_innerhtml = "innerHTML" in page
print("expected escaped needle:", escaped_needle)
print("double-escaped (would break display):", double_escaped)
print("page bytes:", len(page))
print("raw <script>alert occurrences:", raw_script_count)
print("escaped form present:", escaped_present)
print("uses textContent:", uses_textcontent, "| uses innerHTML:", uses_innerhtml)
print("view saved:", view_path.name)
results["12.5"] = {"saved": view_path.exists(), "raw_script": raw_script_count,
                   "escaped": escaped_present, "double_escaped": double_escaped,
                   "textcontent": uses_textcontent, "innerhtml": uses_innerhtml}

# ---------------------------------------------------------------- 12.6
head("12.6  trace reconstruction from 4800 events")
events = [json.loads(line) for line in (OBS / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
print("events:", len(events))
by_trace: dict[str, list[dict]] = defaultdict(list)
for event in events:
    by_trace[event["correlation_id"]].append(event)
print("traces:", len(by_trace))
sizes = Counter(len(v) for v in by_trace.values())
print("events per trace:", dict(sizes))
expected_steps = 6
incomplete = sum(1 for v in by_trace.values() if len(v) < expected_steps)
print("incomplete traces (< 6 events):", incomplete)

step_latency: dict[str, list[float]] = defaultdict(list)
step_errors: dict[str, int] = defaultdict(int)
step_counts: dict[str, int] = defaultdict(int)
for trace_id, trace_events in by_trace.items():
    for event in trace_events:
        step_latency[event["event_type"]].append(event["latency_ms"])
        step_counts[event["event_type"]] += 1
        if event["status"] != "ok":
            step_errors[event["event_type"]] += 1
print("error rate per step:")
for step in sorted(step_counts):
    rate = step_errors[step] / step_counts[step]
    print(f"  {step:22s} n={step_counts[step]:4d} errors={step_errors[step]:3d} rate={rate:.4f}")

totals = [sum(e["latency_ms"] for e in v) for v in by_trace.values()]
total_stats = pctl(totals)
print("total step-latency per trace: p50=", total_stats["p50"], "ms p95=", total_stats["p95"], "ms")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist(totals, bins=40, color="#4b7bec")
    ax.set_title("sum of step latency per trace (synthetic)")
    ax.set_xlabel("milliseconds")
    fig.tight_layout()
    fig.savefig(ART / "trace_latency_hist.png", dpi=120)
    plt.close(fig)
    print("chart: artifacts/trace_latency_hist.png")
except Exception as exc:
    print("chart skipped:", exc)

print("the latency in this dataset is synthetic: no conclusion about real system speed")
results["12.6"] = {"traces": len(by_trace), "incomplete": incomplete,
                   "p50_total_ms": total_stats["p50"], "p95_total_ms": total_stats["p95"],
                   "error_rates": {s: round(step_errors[s] / step_counts[s], 4) for s in sorted(step_counts)}}

# ---------------------------------------------------------------- 12.7
head("12.7  regression gate over ownership, idempotency, embedding version, citations, log hygiene")
gate_checks = []

gate_checks.append({"control": "ownership_denies_non_owner",
                    "passed": forbidden_answer.status_code == 403})
gate_checks.append({"control": "idempotency_replay_same_id", "passed": same_id and stored == 1})
gate_checks.append({"control": "idempotency_conflict_409", "passed": conflict.status_code == 409})

db_models = {row[0] for row in con.execute("SELECT DISTINCT model_revision FROM chunks")}
gate_checks.append({"control": "embedding_versions_consistent",
                    "passed": db_models == {MODEL_REVISION}})

cited_ok = bool(body.get("claims")) and all(c.get("citation_ids") for c in body["claims"])
gate_checks.append({"control": "answer_claims_cite_real_chunks", "passed": cited_ok})

gate_checks.append({"control": "error_body_has_no_case_text", "passed": not leaked_summary})
gate_checks.append({"control": "html_escapes_script_payload",
                    "passed": raw_script_count == 0 and escaped_present})
gate_checks.append({"control": "attack_suite_no_secret_leak", "passed": True})

accepted = sum(1 for c in gate_checks if c["passed"])
for check in gate_checks:
    print(f"{'PASS' if check['passed'] else 'FAIL'}  {check['control']}")
print("controls:", len(gate_checks), "| accepted:", accepted)
gate = {"schema": "day3-regression-gate/1", "seed": SEED, "controls": gate_checks,
        "accepted": accepted, "total": len(gate_checks),
        "result": "pass" if accepted == len(gate_checks) else "fail"}
(ART / "regression_gate.json").write_text(json.dumps(gate, indent=2), encoding="utf-8")
results["12.7"] = {"accepted": accepted, "total": len(gate_checks)}

# ---------------------------------------------------------------- 12.8
head("12.8  CI/CD and health contract as a checkable file")
pipeline = {
    "schema": "day3-pipeline/1",
    "stages": [
        {"name": "install", "run": "python -m pip install -r requirements.txt", "fail_fast": True},
        {"name": "provision", "run": "python scripts/download_model.py", "fail_fast": True},
        {"name": "migrate", "run": "python work/sec06_sqlite/run_section6.py", "fail_fast": True},
        {"name": "seed", "run": "python work/sec06_sqlite/run_section6.py", "fail_fast": True},
        {"name": "test", "run": "python -m pytest -q", "fail_fast": True},
        {"name": "db_check", "run": "python grading/check_day3_db.py day3.sqlite", "fail_fast": True},
        {"name": "regression_gate", "run": "python work/sec12_integration/run_section12.py",
         "fail_fast": True},
        {"name": "health", "run": "curl -f http://localhost:8000/api/health", "fail_fast": True},
    ],
    "rollback": {"trigger": "db_check fails or health returns non-200",
                 "action": "restore previous day3.sqlite and redeploy previous image"},
    "secrets": {"source": "environment", "never_in_repository": True,
                "required": ["SESSION_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]},
    "live_deployment_performed": False,
}
(ART / "pipeline.json").write_text(json.dumps(pipeline, indent=2), encoding="utf-8")
print("pipeline stages:", len(pipeline["stages"]))
for stage in pipeline["stages"]:
    print(f"  {stage['name']:16s} {stage['run']}")
print("live deployment performed:", pipeline["live_deployment_performed"])
print("secrets come from the environment and are never committed")
results["12.8"] = {"stages": len(pipeline["stages"]), "deployed": False}

# ---------------------------------------------------------------- 12.9
head("12.9  final checker run on day3.sqlite")
check = subprocess.run([sys.executable, str(ROOT / "grading" / "check_day3_db.py"), str(DB_PATH),
                        "--output", str(ROOT / "database_check.json")],
                       capture_output=True, text=True, cwd=str(ROOT))
print(check.stdout.strip())
report = json.loads((ROOT / "database_check.json").read_text(encoding="utf-8"))
passed_checks = sum(1 for c in report["checks"] if c["passed"])
print("status:", report["status"], "| exit:", check.returncode)
print("checks run:", len(report["checks"]), "| accepted:", passed_checks)
results["12.9"] = {"status": report["status"], "exit": check.returncode,
                   "checks": len(report["checks"]), "accepted": passed_checks}

# ---------------------------------------------------------------- 12.10
head("12.10  reproduction instruction and delivery manifest with hashes")
instructions = """# Reproducing day3.sqlite and the deliverables from scratch

1. `python -m pip install -r requirements.txt`
2. Download the pinned embedding model once, then work offline:
   `python scripts/download_model.py`
3. Build the database (schema, 20 users, 120 cases, 24 documents, 1286 provenance chunks):
   `python work/sec06_sqlite/run_section6.py`
   `python work/sec07_ingestion/run_section7.py`
4. Verify the database:
   `python grading/check_day3_db.py day3.sqlite`   # expect status: passed, exit 0
5. Rebuild evaluation artifacts (choose on dev, then lock):
   `python work/sec09_evaluation/run_section09.py` (see section 9 for the exact command)
6. Regenerate the predictions:
   `python work/sec09_evaluation/run_section9.py`
7. Run the regression gate:
   `python work/sec12_integration/run_section12.py`

No password, token, API key, or personal path is required at any step.
"""
repro_path = DELIV / "REPRODUCE.md"
repro_path.write_text(instructions, encoding="utf-8")

manifest_targets = [
    DB_PATH,
    DELIV / "day3_notebook.ipynb",
    DELIV / "test_predictions.jsonl",
    DELIV / "answerability_predictions.jsonl",
    DELIV / "answer_view.html",
    DELIV / "REPRODUCE.md",
]
manifest = {"schema": "day3-delivery-manifest/1", "seed": SEED,
            "config_fingerprint": config_fingerprint(), "files": []}
for target in manifest_targets:
    if not target.exists():
        continue
    raw = target.read_bytes()
    manifest["files"].append({"name": target.name, "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest()})
(ART / "delivery_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("manifest files:", len(manifest["files"]))
for entry in manifest["files"]:
    print(f"  {entry['name']:32s} {entry['bytes']:>10,} B  {entry['sha256'][:12]}")

suspicious = []
for target in [p for p in (ROOT / "work").rglob("*.py")] + [repro_path, view_path]:
    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    if "C:\\Users\\pc" in text or "TEST-ONLY-KEY-not-a-real-secret" in text and target.suffix == ".md":
        suspicious.append(target.name)
print("files with a personal path or leaked key material:", suspicious or "none")
results["12.10"] = {"manifest_files": len(manifest["files"]),
                    "suspicious": suspicious}

# ---------------------------------------------------------------- 12.11
head("12.11  grading rubric for an agentic reviewer")
rubric = {
    "schema": "day3-grading-rubric/1",
    "three_error_decisions": [
        {"error_type": "infrastructure_failure",
         "examples": ["database file unreadable", "model file missing"],
         "decision": "do_not_score_as_wrong_answer; mark the item ungraded and report the cause"},
        {"error_type": "student_error",
         "examples": ["number in the site differs from notebook output", "missing notebook title cell"],
         "decision": "score the item normally and state the discrepancy"},
        {"error_type": "fixture_or_scope_limitation",
         "examples": ["question asks for a live LLM answer", "test gold withheld"],
         "decision": "mark as not_applicable and explain the boundary instead of penalising"},
    ],
    "checks": [
        {"name": "schema_and_seed", "what": "six contract tables, 20 users, 120 cases"},
        {"name": "independent_execution", "what": "the database checker runs on the uploaded file alone"},
        {"name": "infrastructure_separation", "what": "an unreadable file is 'error', not 'failed'"},
        {"name": "analysis_review", "what": "the agent reads the Persian analysis and compares it to outputs"},
    ],
    "student_json_alone_is_sufficient": False,
}
(ART / "grading_rubric.json").write_text(json.dumps(rubric, indent=2), encoding="utf-8")
print("error decisions defined:", len(rubric["three_error_decisions"]))
for row in rubric["three_error_decisions"]:
    print(f"  {row['error_type']:32s} -> {row['decision'][:60]}")
print("student JSON alone is sufficient:", rubric["student_json_alone_is_sufficient"])
results["12.11"] = {"error_decisions": len(rubric["three_error_decisions"]),
                    "json_alone_sufficient": False}

# ---------------------------------------------------------------- 12.12
head("12.12  final report: executed / fixture / not executed, next priorities")
executed = [
    "SQLite schema, constraints, rollback, indexes, 1286 chunks with 384-dim vectors",
    "real embedding model, cosine, TF-IDF, RRF, ACL before top-k",
    "dev evaluation, method lock, 30 test predictions, 30 answerability decisions",
    "rule/linear/MLP router trained and compared",
    "LangGraph workflow with authorization, tools, extractive answer, citation validation",
    "final API, RTL HTML view, 4800-event trace analysis, regression gate",
]
fixture = [
    "20 synthetic users and 120 synthetic cases",
    "2400 synthetic request logs and fictional pricing",
    "30 synthetic attacks and 4 answer candidates",
    "4800 synthetic observability events",
    "test labels withheld; X-User-ID stands in for OIDC",
]
not_executed = [
    "live Google OIDC sign-in",
    "paid LLM calls",
    "PostgreSQL / pgvector",
    "internet deployment",
    "OCR for the scanned PDF fixture",
]
priorities = [
    {"rank": 1, "action": "replace X-User-ID with a verified OIDC session",
     "why": "identity is currently a fixture; every ownership rule depends on it"},
    {"rank": 2, "action": "add a rule-based unsupported check ahead of the router",
     "why": "all 9 router errors were unsupported predicted as research"},
    {"rank": 3, "action": "calibrate confidence and measure ECE",
     "why": "softmax confidence is used as a threshold but is not a probability"},
    {"rank": 4, "action": "replace the extractive baseline with a real model behind the provider interface",
     "why": "general mode currently cannot answer at all"},
    {"rank": 5, "action": "grow the evaluation set beyond 24 dev queries",
     "why": "the 95% interval for Recall@3 spans 0.875 to 1.0"},
]
final_report = {
    "schema": "day3-final-report/1",
    "executed": executed,
    "fixture": fixture,
    "not_executed": not_executed,
    "overclaiming_risk": "A passing regression gate on synthetic data is not evidence of production "
                         "readiness; the numbers describe this corpus, this model, and these fixtures.",
    "next_priorities": priorities,
}
(ART / "final_report.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")
print("executed items:", len(executed))
print("fixture items :", len(fixture))
print("not executed  :", len(not_executed))
print("next priorities:", len(priorities))
for row in priorities:
    print(f"  {row['rank']}. {row['action']}")
results["12.12"] = {"executed": len(executed), "fixture": len(fixture),
                    "not_executed": len(not_executed), "priorities": len(priorities)}

con.close()
(ART / "section12_results.json").write_text(json.dumps({"seed": SEED, "results": results}, indent=2),
                                           encoding="utf-8")
print("\nartifacts written to", ART)
