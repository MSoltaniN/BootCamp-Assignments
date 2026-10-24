"""Export every answered question as a browser-fill payload.

Unlike the section 6-12 export, this covers all 144 questions because the
sections 1-4 `دلیل انتخاب` field was only filled after the first pass.

Writes Day4_Run_Output/form_payload_all.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bank = json.loads(
    (ROOT / "docs" / "generated" / "question_bank.json").read_text(encoding="utf-8")
)

payload: dict[str, dict] = {}
for question in bank["questions"]:
    if question["status"] != "answered":
        continue
    # Index by field *id* so the filler never depends on DOM order.
    fields = {
        field["field_id"]: {
            "kind": field["kind"],
            "label": field["label"],
            "answer": field["answer"],
        }
        for field in question["fields"]
    }
    payload[question["id"]] = fields

out = ROOT / "Day4_Run_Output" / "form_payload_all.json"
out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

total_fields = sum(len(v) for v in payload.values())
filled = sum(
    1 for v in payload.values() for f in v.values() if f["answer"] not in (None, "")
)
print(f"questions {len(payload)}  fields {total_fields}  filled {filled}")
print(f"bytes {out.stat().st_size}")
