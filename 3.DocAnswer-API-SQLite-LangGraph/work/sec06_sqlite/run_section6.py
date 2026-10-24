"""Section 6 — SQLite schema, constraints, ownership, tokens, sanitisation, checker.

Run:  .venv\\Scripts\\python.exe work/sec06_sqlite/run_section6.py
Writes: day3.sqlite, work/sec06_sqlite/artifacts/*.json, database_check.json
"""
from __future__ import annotations

import copy
import csv
import json
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from work._common.config import EMBED_DIM, MODEL_ID, MODEL_REVISION, SEED
from work._common.db import (
    SCHEMA,
    connect,
    connect_for_write,
    sha256_text,
    upsert_cases,
    upsert_chunk,
    upsert_document,
    upsert_users,
)
from work._common.paths import APP, CORPUS, CORPUS_RAW, DB_PATH, MANIFEST, OBS
from work.sec06_sqlite.tokens import (
    COOKIE_CONTRACT,
    FIXTURE_SECRET,
    ISSUER,
    LOGIN_SCOPES,
    issue,
    unsign_only,
    verify,
)

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
results: dict = {}

if DB_PATH.exists():
    DB_PATH.unlink()


def head(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


# ---------------------------------------------------------------- 6.1
head("6.1  connect, PRAGMA foreign_keys=ON, SELECT 1, sqlite_version()")
try:
    con = sqlite3.connect(str(DB_PATH), timeout=5.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    with con:
        con.executescript(SCHEMA)
    fk_on = con.execute("PRAGMA foreign_keys").fetchone()[0]
    one = con.execute("SELECT 1").fetchone()[0]
    version = sqlite3.sqlite_version
    connected = fk_on == 1 and one == 1
    print("connected:", connected)
    print("PRAGMA foreign_keys =", fk_on)
    print("SELECT 1 ->", one)
    print("sqlite_version():", version)
    print("connection timeout: 5.0 s")
except sqlite3.Error as exc:                                   # pragma: no cover
    connected, version = False, None
    print("controlled failure:", type(exc).__name__, exc)

# readable error when the file does not exist
try:
    connect(ROOT / "does_not_exist.sqlite")
    bad_file_message = "no error (unexpected)"
except (FileNotFoundError, ValueError) as exc:
    bad_file_message = f"{type(exc).__name__}: {exc}"
print("missing-file handling:", bad_file_message)
print("no synthetic success is reported when the file cannot be opened")
results["6.1"] = {"connected": connected, "sqlite_version": version,
                  "missing_file": bad_file_message, "timeout_seconds": 5.0}

# ---------------------------------------------------------------- 6.2
head("6.2  contract tables + idempotent seed of 20 users and 120 cases")
users = list(csv.DictReader((APP / "users.csv").open(encoding="utf-8")))
cases = [json.loads(line) for line in (APP / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
print("source users:", len(users), "| source cases:", len(cases))

for run in (1, 2):
    with con:
        n_users = upsert_users(con, users)
        n_cases = upsert_cases(con, cases)
    print(f"seed run {run}: users={n_users} cases={n_cases}")
print("rerun created no duplicates" if (n_users, n_cases) == (20, 120) else "SEED PROBLEM")
results["6.2"] = {"users": n_users, "cases": n_cases, "idempotent": (n_users, n_cases) == (20, 120)}

# ---------------------------------------------------------------- 6.3
head("6.3  foreign key rejects an orphan case owner, connection still usable")
before = con.execute("SELECT count(*) FROM cases").fetchone()[0]
rejected = False
try:
    with con:
        con.execute(
            "INSERT INTO cases (case_id, owner_id, topic, summary) VALUES (?,?,?,?)",
            ("C-ORPHAN", "U-NOT-EXIST", "test", "orphan probe"),
        )
except sqlite3.IntegrityError as exc:
    rejected = "FOREIGN KEY" in str(exc).upper()
    print("IntegrityError:", exc)
after = con.execute("SELECT count(*) FROM cases").fetchone()[0]
still_usable = con.execute("SELECT count(*) FROM users").fetchone()[0] == 20
print("orphan rejected:", rejected)
print("cases before/after:", before, after)
print("connection usable afterwards:", still_usable)
results["6.3"] = {"rejected": rejected, "cases_before": before, "cases_after": after,
                  "connection_usable": still_usable}

# ---------------------------------------------------------------- 6.4
head("6.4  transaction rollback: valid session then message with a bad session_id")
writer = connect_for_write(DB_PATH)
sessions_before = writer.execute("SELECT count(*) FROM sessions").fetchone()[0]
try:
    writer.execute("BEGIN")
    sid = f"S-{uuid.uuid4().hex[:8]}"
    writer.execute(
        "INSERT INTO sessions (session_id, owner_id, case_id, idempotency_key) VALUES (?,?,?,?)",
        (sid, "U-002", "C-001", f"tx-{sid}"),
    )
    writer.execute(
        "INSERT INTO messages (message_id, session_id, content) VALUES (?,?,?)",
        (f"M-{uuid.uuid4().hex[:8]}", "S-NOT-A-SESSION", "boom"),
    )
    writer.execute("COMMIT")
    rolled_back = False
except sqlite3.IntegrityError as exc:
    writer.execute("ROLLBACK")
    rolled_back = "FOREIGN KEY" in str(exc).upper()
    print("IntegrityError:", exc)
sessions_after = writer.execute("SELECT count(*) FROM sessions").fetchone()[0]
print("sessions before/after:", sessions_before, sessions_after)
print("whole transaction rolled back:", rolled_back and sessions_before == sessions_after)
writer.close()
results["6.4"] = {"rolled_back": rolled_back, "sessions_before": sessions_before,
                  "sessions_after": sessions_after,
                  "atomic": rolled_back and sessions_before == sessions_after}

# ---------------------------------------------------------------- 6.5
head("6.5  parameterised query vs SQL injection string")
attack = "U-002' OR '1'='1"
total_users = con.execute("SELECT count(*) FROM users").fetchone()[0]
safe_rows = con.execute("SELECT user_id FROM users WHERE user_id = ?", (attack,)).fetchall()
naive_sql = f"SELECT user_id FROM users WHERE user_id = '{attack}'"
try:
    naive_rows = con.execute(naive_sql).fetchall()
except sqlite3.Error as exc:
    naive_rows = []
    print("unsafe query error:", exc)
print("attack string:", attack)
print("parameterised matches:", len(safe_rows), "(treated as a value)")
print("string-concatenated matches:", len(naive_rows), "(treated as SQL)")
print("users total before/after:", total_users, con.execute("SELECT count(*) FROM users").fetchone()[0])
results["6.5"] = {"attack_matches_parameterised": len(safe_rows),
                  "attack_matches_concatenated": len(naive_rows),
                  "users_unchanged": con.execute("SELECT count(*) FROM users").fetchone()[0] == total_users}

# ---------------------------------------------------------------- 6.6
head("6.6  ownership logic: owner, other student, admin")
class SQLiteAdapter:
    """The adapter the final API uses; ownership is decided here, not in the UI."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.con = connection

    def user(self, user_id: str) -> dict | None:
        row = self.con.execute("SELECT user_id, role, tenant FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def read_case(self, user_id: str, case_id: str) -> tuple[int, dict | None]:
        user = self.user(user_id)
        if user is None:
            return 401, None
        row = self.con.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            return 404, None
        case = dict(row)
        if user["role"] == "admin" or case["owner_id"] == user_id:
            return 200, case
        return 403, None


adapter = SQLiteAdapter(con)
scenarios = [("U-002", "owner of C-001"), ("U-003", "other student"), ("U-000", "admin")]
table_66 = []
for user_id, label in scenarios:
    status, case = adapter.read_case(user_id, "C-001")
    role = adapter.user(user_id)["role"]
    print(f"{user_id:6s} ({role:7s}) {label:16s} -> {status}")
    table_66.append({"user_id": user_id, "role": role, "label": label, "status": status})
results["6.6"] = table_66

# ---------------------------------------------------------------- 6.7
head("6.7  owner_id index and EXPLAIN QUERY PLAN")
indexes = [dict(r) for r in con.execute('PRAGMA index_list("cases")')]
owner_index = any(
    [c["name"] for c in con.execute(f'PRAGMA index_info("{idx["name"]}")')][:1] == ["owner_id"]
    for idx in indexes
)
plan = con.execute("EXPLAIN QUERY PLAN SELECT case_id FROM cases WHERE owner_id = ?", ("U-002",)).fetchall()
plan_lines = [tuple(r)[-1] for r in plan]
print("index on cases.owner_id:", owner_index)
for line in plan_lines:
    print("  plan:", line)
print("first plan line:", plan_lines[0] if plan_lines else None)
results["6.7"] = {"owner_index": owner_index, "first_plan_line": plan_lines[0] if plan_lines else None,
                  "plan": plan_lines}

# ---------------------------------------------------------------- 6.8
head("6.8  document metadata UPSERT twice + real 384-dim vectors stored in the file")
docs = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
print("manifest documents:", len(docs))

from sentence_transformers import SentenceTransformer  # local, offline after download

model = SentenceTransformer(str(ROOT / "resources" / "embedding_model"), device="cpu")
print("embedding model:", MODEL_ID, "| dim:", model.get_embedding_dimension(),
      "| max_seq_length:", model.max_seq_length)

doc_rows = []
pending = []
for row in docs:
    raw_path = CORPUS / row["path"]
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    doc_rows.append({
        "doc_id": row["doc_id"], "version": row["version"], "content_hash": row["sha256"],
        "title": row["title"], "path": row["path"], "source_url": row["source_url"],
        "access": row["access"], "tenant": row["tenant"],
        "license": row["license"], "source_type": row["source_type"],
    })
    # Provisional one-chunk-per-document seed. Section 7 replaces this with 220/40 token chunks;
    # here it exists so the file has real 384-dim vectors and the checker can pass.
    pending.append((row, text[:1500]))

# Encode as a batch: encoding a single string returns shape (384,), not (1, 384).
matrix = model.encode([content for _, content in pending], batch_size=32,
                      normalize_embeddings=True, convert_to_numpy=True)
assert matrix.shape == (len(pending), EMBED_DIM), matrix.shape

chunk_rows = []
for (row, content), vector in zip(pending, matrix):
    chunk_rows.append({
        "chunk_id": f"{row['doc_id']}:v{row['version'][:8]}:0",
        "doc_id": row["doc_id"], "chunk_index": 0, "content": content,
        "start_char": 0, "end_char": len(content), "content_hash": sha256_text(content),
        "embedding": vector.astype("float32").tobytes(),
        "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
    })

for run in (1, 2):
    with con:
        for doc in doc_rows:
            upsert_document(con, doc)
        for chunk in chunk_rows:
            upsert_chunk(con, chunk)
    n_docs = con.execute("SELECT count(*) FROM documents").fetchone()[0]
    n_chunks = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"upsert run {run}: documents={n_docs} chunks={n_chunks}")
print("vector bytes per chunk:", len(chunk_rows[0]["embedding"]), "=", EMBED_DIM * 4)
print("model metadata rows complete:",
      con.execute("SELECT count(*) FROM chunks WHERE model_id IS NULL OR model_id='' "
                  "OR model_revision IS NULL OR model_revision=''").fetchone()[0] == 0)
results["6.8"] = {"documents_after_two_upserts": n_docs, "chunks": n_chunks,
                  "vectors_in_file": True, "vector_bytes": len(chunk_rows[0]["embedding"]),
                  "model_id": MODEL_ID, "model_revision": MODEL_REVISION}

# ---------------------------------------------------------------- 6.9
head("6.9  signed test tokens: signature, issuer, audience, expiry")
valid = issue("U-002")
bad_issuer = issue("U-002", issuer="https://evil.example.test")
bad_audience = issue("U-002", audience="some-other-client")
expired = issue("U-002", expires_in=-10)
tampered = valid[:-4] + ("aaaa" if not valid.endswith("aaaa") else "bbbb")

cases_69 = [
    ("valid", valid, True),
    ("wrong issuer", bad_issuer, False),
    ("wrong audience", bad_audience, False),
    ("expired", expired, False),
    ("tampered signature", tampered, False),
]
rejected = 0
for label, token, should_pass in cases_69:
    result = verify(token)
    print(f"{label:20s} ok={str(result.ok):5s} reason={result.reason:15s} expected_ok={should_pass}")
    if not result.ok and not should_pass:
        rejected += 1
print("invalid tokens rejected:", rejected)
print("naive decode would have accepted the expired token:",
      unsign_only(expired).get("sub"), "(no signature/expiry check)")
results["6.9"] = {"invalid_rejected": rejected, "cases": len(cases_69) - 1,
                  "valid_accepted": verify(valid).ok}

# ---------------------------------------------------------------- 6.10
head("6.10  login scope and cookie contract (config, no real secret)")
cookie_ok = all([COOKIE_CONTRACT["httponly"], COOKIE_CONTRACT["secure"],
                 COOKIE_CONTRACT["samesite"] in {"Lax", "Strict"}])
print("login scopes:", LOGIN_SCOPES)
print("cookie contract:", json.dumps(COOKIE_CONTRACT, indent=2))
print("email report consent is a separate flag; the app keeps working when it is off")
config_610 = {
    "login_scopes": LOGIN_SCOPES,
    "cookie": COOKIE_CONTRACT,
    "email_report": {"requires_explicit_consent": True, "scope": "https://www.googleapis.com/auth/gmail.send",
                     "disabling_keeps_app_working": True},
    "secrets_from_environment": ["SESSION_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
    "client_secret_in_artifact": False,
}
(ART / "auth_config.json").write_text(json.dumps(config_610, indent=2), encoding="utf-8")
print("config written to artifacts/auth_config.json")
results["6.10"] = {"scopes": LOGIN_SCOPES, "secure_and_httponly": cookie_ok,
                   "same_site": COOKIE_CONTRACT["samesite"]}

# ---------------------------------------------------------------- 6.11
head("6.11  recursive sanitisation of nested metadata")
SENSITIVE = {"api_key", "apikey", "api-key", "authorization", "token", "access_token",
             "refresh_token", "password", "secret", "client_secret", "cookie", "set-cookie"}


def sanitise(value):
    """Walk dicts and lists; drop sensitive keys at any depth, mask embedded secrets in strings."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE:
                continue
            out[key] = sanitise(item)
        return out
    if isinstance(value, list):
        return [sanitise(item) for item in value]
    if isinstance(value, str) and "TEST-ONLY-SECRET" in value:
        return "[REDACTED]"
    return value


events = [json.loads(line) for line in (OBS / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
with_secret = [e for e in events if "TEST-ONLY-SECRET" in json.dumps(e)]
nested_demo = {
    "event_type": "retrieval_completed",
    "metadata": {"api_key": "TEST-ONLY-SECRET", "prompt_version": "v1",
                 "provider": {"name": "provider_a", "credentials": {"api_key": "TEST-ONLY-SECRET"}},
                 "history": [{"api_key": "TEST-ONLY-SECRET"}, {"note": "kept TEST-ONLY-SECRET inside text"}]},
}
cleaned_demo = sanitise(nested_demo)
print("events scanned:", len(events), "| events containing the test secret:", len(with_secret))
print("nested sample before:", json.dumps(nested_demo, ensure_ascii=False))
print("nested sample after :", json.dumps(cleaned_demo, ensure_ascii=False))

cleaned_events = [sanitise(e) for e in events]
remaining = sum(1 for e in cleaned_events if "TEST-ONLY-SECRET" in json.dumps(e))
print("remaining test secret occurrences across all events:", remaining)
(ART / "sanitised_events.jsonl").write_text(
    "\n".join(json.dumps(e, ensure_ascii=False) for e in cleaned_events[:200]), encoding="utf-8")
print("first 200 sanitised events written to artifacts/sanitised_events.jsonl")
results["6.11"] = {"events_scanned": len(events), "events_with_secret": len(with_secret),
                   "remaining_after": remaining, "nested_removed": "TEST-ONLY-SECRET" not in json.dumps(cleaned_demo)}

con.close()

# ---------------------------------------------------------------- 6.12
head("6.12  check_day3_db.py on day3.sqlite, plus the three exit codes")
checker = ROOT / "grading" / "check_day3_db.py"
run = subprocess.run([sys.executable, str(checker), str(DB_PATH), "--output", str(ROOT / "database_check.json")],
                     capture_output=True, text=True, cwd=str(ROOT))
print(run.stdout.strip())
report = json.loads((ROOT / "database_check.json").read_text(encoding="utf-8"))
passed_checks = sum(1 for c in report["checks"] if c["passed"])
print("status:", report["status"], "| exit code:", run.returncode,
      "| checks:", len(report["checks"]), "| passed:", passed_checks)

# demonstrate the other two exit codes on throwaway files
scratch = ART / "_scratch"
scratch.mkdir(exist_ok=True)
not_sqlite = scratch / "not_a_database.sqlite"
not_sqlite.write_text("this is not a database", encoding="utf-8")
broken = scratch / "empty_schema.sqlite"
empty = sqlite3.connect(broken)
empty.execute("CREATE TABLE t (x INTEGER)")
empty.commit()
empty.close()

code_2 = subprocess.run([sys.executable, str(checker), str(not_sqlite), "--output", str(scratch / "r2.json")],
                        capture_output=True, text=True).returncode
code_1 = subprocess.run([sys.executable, str(checker), str(broken), "--output", str(scratch / "r1.json")],
                        capture_output=True, text=True).returncode
print("exit code for a non-SQLite file:", code_2, "(status error)")
print("exit code for a SQLite file without the contract tables:", code_1, "(status failed)")
results["6.12"] = {"exit_code": run.returncode, "status": report["status"],
                   "checks_run": len(report["checks"]), "checks_passed": passed_checks,
                   "error_exit": code_2, "failed_exit": code_1}

(ART / "section6_results.json").write_text(json.dumps({"seed": SEED, "database": str(DB_PATH.name),
                                                        "results": results}, indent=2), encoding="utf-8")
print("\nartifacts written to", ART)
