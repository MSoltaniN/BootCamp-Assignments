"""Cross-check the form scraped from the site against the grading schema.

`docs/questions.json` is parsed out of the saved mission page; the pack ships the
authoritative `Day4_Grading/question_schema.json`. They must agree on question
ids, scores, field kinds and choice options. Any drift means the site form was
updated after the pack (or the parser is wrong), and both are worth knowing
before answering.

Writes `docs/_reconcile.txt` and exits non-zero when a mismatch is found.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "generated" / "questions.json"
OFFICIAL = (
    ROOT / "assignment" / "source" / "Day4" / "Day4_Grading" / "question_schema.json"
)

# The HTML only knows "radio", "input" and "textarea". The grading schema is
# finer-grained: it splits plain inputs into "short" (free text) and "number"
# (numeric), and names textareas "textarea". Because the page markup cannot tell
# short from number, kind comparison is done at the coarse level here; the
# authoritative per-field kind is merged in by `enrich_questions.py`.
KIND_ALIASES = {"radio": "choice", "input": "input", "textarea": "textarea"}
COARSE = {"choice": "choice", "short": "input", "number": "input", "textarea": "textarea"}

site = json.loads(SITE.read_text(encoding="utf-8"))
official = json.loads(OFFICIAL.read_text(encoding="utf-8"))

site_q = {q["id"]: q for q in site["questions"]}
official_q = {}
for section in official:
    for question in section["questions"]:
        official_q[question["id"]] = question

lines: list[str] = []
add = lines.append
problems = 0

add(f"site questions    : {len(site_q)}")
add(f"official questions: {len(official_q)}")
add("")

missing_in_site = sorted(set(official_q) - set(site_q), key=lambda s: [int(x) for x in s.split(".")])
missing_in_official = sorted(set(site_q) - set(official_q), key=lambda s: [int(x) for x in s.split(".")])
add(f"missing in site     : {missing_in_site or 'none'}")
add(f"missing in official : {missing_in_official or 'none'}")
problems += len(missing_in_site) + len(missing_in_official)
add("")

add("== PER-QUESTION DIFFS ==")
for qid in sorted(set(site_q) & set(official_q), key=lambda s: [int(x) for x in s.split(".")]):
    mine = site_q[qid]
    theirs = official_q[qid]
    diffs: list[str] = []

    if abs(mine["points"] - float(theirs["score"])) > 1e-9:
        diffs.append(f"score {mine['points']} != {theirs['score']}")

    if mine["prompt"].strip() != theirs["prompt"].strip():
        mine_prompt = mine["prompt"].replace("\u200c", "")
        their_prompt = theirs["prompt"].replace("\u200c", "")
        if mine_prompt.strip() != their_prompt.strip():
            diffs.append("prompt text differs")

    mine_fields = [(KIND_ALIASES.get(f["kind"], f["kind"]), f["label"], tuple(f["choices"]))
                   for f in mine["fields"]]
    their_fields = [(COARSE.get(f["kind"], f["kind"]), f["label"], tuple(f.get("options", [])))
                    for f in theirs["fields"]]

    if len(mine_fields) != len(their_fields):
        diffs.append(f"field count {len(mine_fields)} != {len(their_fields)}")
    else:
        for index, (a, b) in enumerate(zip(mine_fields, their_fields)):
            if a[0] != b[0]:
                diffs.append(f"field[{index}] kind {a[0]} != {b[0]}")
            if a[1].strip() != b[1].strip():
                diffs.append(f"field[{index}] label {a[1]!r} != {b[1]!r}")
            if a[2] != b[2]:
                diffs.append(f"field[{index}] options {a[2]} != {b[2]}")

    if diffs:
        problems += 1
        add(f"--- {qid}")
        for diff in diffs:
            add(f"    {diff}")

if not problems:
    add("no differences found -- site form matches the official schema exactly")

add("")
add(f"TOTAL PROBLEMS: {problems}")

out = ROOT / "docs" / "generated" / "qa" / "_reconcile.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out}; problems={problems}")
sys.exit(0 if problems == 0 else 1)
