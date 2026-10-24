"""Inspect the application DB against the checker's three failing conditions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
db = sqlite3.connect(ROOT / "Day4_Run_Output" / "application.sqlite")
db.row_factory = sqlite3.Row

lines: list[str] = []


def emit(text: str) -> None:
    lines.append(text)


emit("== WRITES ==")
for row in db.execute("SELECT * FROM writes"):
    emit(f"  key={row['idempotency_key']} v={row['version']} "
         f"hash={row['payload_hash'][:12]} approval={row['approval_id']}")

emit("== APPROVALS ==")
for row in db.execute("SELECT * FROM approvals"):
    emit(f"  {row['approval_id']} base={row['base_version']} "
         f"hash={row['payload_hash'][:12]} approved={row['approved']} "
         f"rev={row['reviewer']}")

emit("== PROFILES ==")
for row in db.execute("SELECT * FROM profiles"):
    body = json.loads(row["payload"])
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    emit(f"  {row['employee_id']} v={row['version']} keys={sorted(body)}")
    emit(f"    body_hash={hashlib.sha256(canonical.encode()).hexdigest()[:12]}")

emit("== MEMORIES ==")
for row in db.execute("SELECT * FROM memories"):
    emit(f"  emp={row['employee_id']} ev={row['evidence_id']} "
         f"exp={row['expires_day']} type={type(row['expires_day']).__name__}")
    emit(f"    text={row['text']!r}")

emit("== JOBS ==")
emit(f"  count={db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]}")
for row in db.execute("SELECT * FROM jobs LIMIT 3"):
    emit(f"  key={row['event_key']!r} status={row['status']!r}")

emit("== JOBS SCHEMA ==")
for row in db.execute("PRAGMA table_info(jobs)"):
    emit(f"  {row['name']} pk={row['pk']}")

emit("== AUDIT ==")
for row in db.execute("SELECT action, COUNT(*) c FROM audit GROUP BY action"):
    emit(f"  {row['action']} x{row['c']}")

Path(ROOT / "scripts" / "_db_debug.txt").write_text("\n".join(lines), encoding="utf-8")
print("written")
