"""Write a UTF-8 QA report for the parsed question bank.

The Windows console defaults to cp1256 and cannot print Persian, so this report
goes to `docs/_extraction_report.txt` instead of stdout.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
bank = json.loads((GEN / "questions.json").read_text(encoding="utf-8"))
questions = bank["questions"]

lines: list[str] = []
add = lines.append

totals = bank["totals"]
add("== TOTALS ==")
for key, value in totals.items():
    add(f"{key:<14}: {value}")
add("")

add("== SECTIONS ==")
for section in bank["sections"]:
    group = [q for q in questions if q["section"] == section["number"]]
    pts = sum(q["points"] for q in group)
    add(f"[{section['number']}] {section['title']}  ->  {len(group)} q / {pts:g} pts")
    add(f"    meta: {section['meta']}")
add("")

add("== HEALTH ==")
add(f"missing prompt     : {[q['id'] for q in questions if not q['prompt']] or 'none'}")
add(f"no fields          : {[q['id'] for q in questions if not q['fields']] or 'none'}")
add(f"text label missing : {[f['id'] for q in questions for f in q['fields'] if f['kind'] != 'radio' and not f['label']] or 'none'}")
add(f"radio label missing: {[f['id'] for q in questions for f in q['fields'] if f['kind'] == 'radio' and not f['label']] or 'none'}")
add(f"radio w/o choices  : {[f['id'] for q in questions for f in q['fields'] if f['kind'] == 'radio' and not f['choices']] or 'none'}")
add(f"non yes/no radios  : {[ (f['id'], f['choices']) for q in questions for f in q['fields'] if f['kind'] == 'radio' and set(f['choices']) - {'بله','خیر'}] or 'none'}")
add("")

add("== TYPES ==")
for kind, freq in Counter(q["type"] for q in questions).items():
    add(f"{kind:<20}: {freq}")
add("")
add("== POINTS ==")
for pts, freq in sorted(Counter(q["points"] for q in questions).items()):
    add(f"{pts:g} points -> {freq} questions")
add("")
add("== FIELD LABELS (top 30 by frequency) ==")
for label, freq in Counter(f["label"] for q in questions for f in q["fields"]).most_common(30):
    add(f"{freq:>4}x  {label or '(EMPTY)'}")
add("")

add("== SAMPLE: section 5 (first 4 questions, full) ==")
for q in [x for x in questions if x["section"] == "5"][:4]:
    add(f"--- {q['id']} ({q['points']:g} pts, {q['type']}, {len(q['fields'])} fields)")
    add(f"prompt: {q['prompt']}")
    for field in q["fields"]:
        if field["kind"] == "radio":
            add(f"   [radio] {field['label']}  ->  {' / '.join(field['choices'])}")
        else:
            add(f"   [{field['kind']:<8}] {field['label']}")
    add("")

add("== SAMPLE: section 12 (last 3 questions, full) ==")
for q in [x for x in questions if x["section"] == "12"][-3:]:
    add(f"--- {q['id']} ({q['points']:g} pts, {q['type']}, {len(q['fields'])} fields)")
    add(f"prompt: {q['prompt']}")
    for field in q["fields"]:
        if field["kind"] == "radio":
            add(f"   [radio] {field['label']}  ->  {' / '.join(field['choices'])}")
        else:
            add(f"   [{field['kind']:<8}] {field['label']}")
    add("")

out = GEN / "qa" / "_extraction_report.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print(f"report: {out} ({out.stat().st_size} bytes)")
