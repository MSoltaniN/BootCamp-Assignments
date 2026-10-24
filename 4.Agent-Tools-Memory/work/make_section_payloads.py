"""Build one gzip+base64 payload per section.

Each file is small enough that a single read + single browser paste can carry it,
which removes the need for chunking or a transfer bridge.

Writes Day4_Run_Output/payload_sec<NN>.b64
"""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bank = json.loads(
    (ROOT / "docs" / "generated" / "question_bank.json").read_text(encoding="utf-8")
)

by_section: dict[str, dict] = {}
for question in bank["questions"]:
    if question["status"] != "answered":
        continue
    fields = {}
    for index, field in enumerate(question["fields"]):
        fields[str(index)] = {
            "field_id": field["field_id"],
            "kind": field["kind"],
            "label": field["label"],
            "options": field["options"],
            "answer": field["answer"],
        }
    by_section.setdefault(question["section"], {})[question["id"]] = fields

out_dir = ROOT / "Day4_Run_Output"

# Wrap at 1800 chars so `read_file` (which truncates long lines) returns every
# character intact and the value can be pasted into the browser verbatim.
WIDTH = 1800

for section, payload in sorted(by_section.items(), key=lambda kv: int(kv[0])):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    packed = gzip.compress(raw, compresslevel=9)
    encoded = base64.b64encode(packed).decode("ascii")
    wrapped = "\n".join(
        encoded[i : i + WIDTH] for i in range(0, len(encoded), WIDTH)
    )
    path = out_dir / f"payload_sec{int(section):02d}.b64"
    path.write_text(wrapped, encoding="utf-8")
    lines = wrapped.count("\n") + 1
    print(f"section {section:>2}: q={len(payload):>2} raw={len(raw):>6} "
          f"b64={len(encoded):>5} lines={lines}")
