"""Run every sub-question handler once, outside Jupyter, to catch shape errors before executing.

Prints one line per failure instead of aborting on the first, so a single pass finds them all.
"""
from __future__ import annotations

import io
import json
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from work.notebook_support import show

questions = json.loads((ROOT / "artifacts" / "questions.json").read_text(encoding="utf-8"))
ids = [q["id"] for section in questions["sections"] for q in section["questions"]]
print("sub-questions:", len(ids))

failures = []
empty_outputs = []
for qid in ids:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            show(qid)
        text = buffer.getvalue()
        body = text.split("\n", 1)[1].strip() if "\n" in text else ""
        if not body:
            empty_outputs.append(qid)
    except Exception:
        failures.append((qid, traceback.format_exc().splitlines()[-1]))

print("failures:", len(failures))
for qid, message in failures:
    print(f"  {qid}: {message}")
print("empty outputs:", len(empty_outputs), empty_outputs[:10])
raise SystemExit(1 if failures else 0)
