"""Verify and stage the files for the four upload cards.

Checks each artifact against the contract before copying it to `final_upload/`, so a bad file is
caught here rather than after submission. Writes a short report next to the copies.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIV = ROOT / "deliverables"
OUT = ROOT / "final_upload"
DB = ROOT / "day3.sqlite"
NOTEBOOK = DELIV / "day3_notebook.ipynb"

DIM = 384
checks: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    checks.append((name, bool(passed), detail))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ notebook
def verify_notebook() -> None:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = nb["cells"]
    titles = [c for c in cells
              if c["cell_type"] == "markdown" and "".join(c["source"]).startswith("## زیرسؤال")]
    code = [c for c in cells if c["cell_type"] == "code"]
    with_output = [c for c in code if c.get("outputs")]
    raw = NOTEBOOK.read_text(encoding="utf-8")

    check("notebook: 144 titled sub-questions", len(titles) == 144, f"{len(titles)}")
    check("notebook: every code cell has output", len(with_output) == len(code),
          f"{len(with_output)}/{len(code)}")
    check("notebook: no personal path", "C:\\Users\\pc" not in raw and "C:/Users/pc" not in raw)
    check("notebook: no secret marker in stored output",
          "TEST-ONLY-SECRET" not in json.dumps([c.get("outputs") for c in code]))
    check("notebook: Persian separator U+066B used in titles",
          all("\u066b" in "".join(c["source"]).split("\n")[0] for c in titles))


# ------------------------------------------------------------------ database
def verify_database() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    users = con.execute("SELECT count(*) FROM users").fetchone()[0]
    cases = con.execute("SELECT count(*) FROM cases").fetchone()[0]
    docs = con.execute("SELECT count(*) FROM documents").fetchone()[0]
    chunks = con.execute("SELECT count(*) FROM chunks").fetchone()[0]

    bad_dim = 0
    meta_missing = 0
    for row in con.execute("SELECT embedding, model_id, model_revision FROM chunks"):
        raw = row["embedding"]
        if raw is None or len(bytes(raw)) != DIM * 4:
            bad_dim += 1
        if not (row["model_id"] or "").strip() or not (row["model_revision"] or "").strip():
            meta_missing += 1
    size_mb = DB.stat().st_size / (1024 * 1024)

    check("db: users == 20", users == 20, str(users))
    check("db: cases == 120", cases == 120, str(cases))
    check("db: documents >= 24", docs >= 24, str(docs))
    check("db: chunks >= max(24, docs)", chunks >= max(24, docs), str(chunks))
    check("db: every embedding is 384 float32", bad_dim == 0, f"{bad_dim} bad")
    check("db: model metadata present on every chunk", meta_missing == 0, f"{meta_missing} missing")
    check("db: under the 80 MB upload limit", size_mb < 80, f"{size_mb:.2f} MB")
    con.close()


# ------------------------------------------------------------------ predictions
def verify_predictions() -> None:
    queries = [json.loads(line) for line in
               (ROOT / "datasets" / "02_Evaluation" / "queries.jsonl").read_text(encoding="utf-8").splitlines()
               if line]
    test_ids = {q["query_id"] for q in queries if q["split"] == "test"}
    doc_con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    known_docs = {row[0] for row in doc_con.execute("SELECT doc_id FROM documents")}
    doc_con.close()

    retrieval = [json.loads(line) for line in
                 (DELIV / "test_predictions.jsonl").read_text(encoding="utf-8").splitlines() if line]
    check("retrieval: 30 lines", len(retrieval) == 30, str(len(retrieval)))
    check("retrieval: every query_id is a test query",
          all(r["query_id"] in test_ids for r in retrieval))
    check("retrieval: three distinct doc ids per row",
          all(len(r["ranked_doc_ids"]) == 3 and len(set(r["ranked_doc_ids"])) == 3 for r in retrieval))
    check("retrieval: every doc id exists in the database",
          all(d in known_docs for r in retrieval for d in r["ranked_doc_ids"]))
    check("retrieval: no labels leaked into the file",
          all(set(r) == {"query_id", "ranked_doc_ids"} for r in retrieval))

    answerability = [json.loads(line) for line in
                     (DELIV / "answerability_predictions.jsonl").read_text(encoding="utf-8").splitlines() if line]
    check("answerability: 30 lines", len(answerability) == 30, str(len(answerability)))
    check("answerability: every query_id is a test query",
          all(r["query_id"] in test_ids for r in answerability))
    check("answerability: score is a finite float",
          all(isinstance(r["score"], (int, float)) and 0.0 <= r["score"] <= 1.0 for r in answerability))
    check("answerability: accepted is boolean",
          all(isinstance(r["accepted"], bool) for r in answerability))
    check("answerability: same query set as retrieval",
          {r["query_id"] for r in answerability} == {r["query_id"] for r in retrieval})


def main() -> int:
    verify_notebook()
    verify_database()
    verify_predictions()

    OUT.mkdir(exist_ok=True)
    mapping = [
        (NOTEBOOK, "1_notebook.ipynb"),
        (DB, "2_day3.sqlite"),
        (DELIV / "test_predictions.jsonl", "3_test_predictions.jsonl"),
        (DELIV / "answerability_predictions.jsonl", "4_answerability_predictions.jsonl"),
    ]
    staged = []
    for source, name in mapping:
        target = OUT / name
        shutil.copy2(source, target)
        staged.append({"file": name, "source": str(source.relative_to(ROOT)),
                       "bytes": target.stat().st_size, "sha256": sha256(target)})

    passed = sum(1 for _, ok, _ in checks if ok)
    print("=" * 72)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    print("=" * 72)
    print(f"checks passed: {passed}/{len(checks)}")
    print()
    for row in staged:
        print(f"{row['file']:<34} {row['bytes']:>10,} B  {row['sha256'][:16]}")

    report = {"checks_passed": passed, "checks_total": len(checks),
              "all_passed": passed == len(checks),
              "details": [{"check": n, "passed": o, "detail": d} for n, o, d in checks],
              "files": staged}
    (OUT / "_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
