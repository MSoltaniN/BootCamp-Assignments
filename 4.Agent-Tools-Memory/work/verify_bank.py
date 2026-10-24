"""Verify the bank against the official schema, in one place.

Checks, for all 144 questions:
  * every question is `answered`
  * every field has a non-null answer
  * choice answers are one of that field's own options
  * number answers are numeric
  * text slots are non-empty
  * points sum to 100

Writes docs/generated/qa/_bank_verify.txt and exits non-zero on any failure.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "docs" / "generated" / "question_bank.json"
OUT = ROOT / "docs" / "generated" / "qa" / "_bank_verify.txt"


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    questions = bank["questions"]

    lines: list[str] = ["== BANK VERIFICATION ==", ""]
    problems: list[str] = []

    unanswered = [q["id"] for q in questions if q["status"] != "answered"]
    if unanswered:
        problems.append(f"unanswered: {unanswered}")

    empty_fields: list[str] = []
    bad_choices: list[str] = []
    bad_numbers: list[str] = []
    empty_text: list[str] = []

    for question in questions:
        for index, field in enumerate(question["fields"]):
            answer = field["answer"]
            if answer is None or (isinstance(answer, str) and not answer.strip()):
                empty_fields.append(f"{question['id']}[{index}] {field['label']}")
                continue
            if field["kind"] == "choice" and answer not in field["options"]:
                bad_choices.append(f"{question['id']}[{index}] {answer!r}")
            elif field["kind"] == "number" and (
                not isinstance(answer, (int, float)) or isinstance(answer, bool)
            ):
                bad_numbers.append(f"{question['id']}[{index}] {answer!r}")

    total_points = sum(q["points"] for q in questions)
    per_section: dict[str, float] = {}
    for question in questions:
        per_section[question["section"]] = (
            per_section.get(question["section"], 0.0) + question["points"]
        )

    lines.append(f"questions        : {len(questions)}")
    lines.append(f"answered         : {len(questions) - len(unanswered)}")
    lines.append(f"total points     : {total_points:g}")
    lines.append(f"empty fields     : {len(empty_fields)}")
    lines.append(f"invalid choices  : {len(bad_choices)}")
    lines.append(f"invalid numbers  : {len(bad_numbers)}")
    lines.append("")
    lines.append("== POINTS BY SECTION ==")
    for section in sorted(per_section, key=int):
        count = sum(1 for q in questions if q["section"] == section)
        lines.append(f"  section {section:>2}: {count:>3} q  {per_section[section]:>5g} pts")
    lines.append("")
    lines.append("== ANSWER TYPES ==")
    kinds = Counter(
        field["kind"] for q in questions for field in q["fields"] if field["answer"] is not None
    )
    for kind, count in sorted(kinds.items()):
        lines.append(f"  {kind:<10}: {count}")

    for label, items in (
        ("unanswered", unanswered),
        ("empty fields", empty_fields),
        ("invalid choices", bad_choices),
        ("invalid numbers", bad_numbers),
        ("empty text", empty_text),
    ):
        if items:
            lines.append("")
            lines.append(f"== {label.upper()} ==")
            lines += [f"  {item}" for item in items[:40]]

    ok = not (unanswered or empty_fields or bad_choices or bad_numbers) and abs(total_points - 100) < 1e-9
    lines += ["", "RESULT: " + ("PASS" if ok else "FAIL")]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"questions {len(questions)}  points {total_points:g}  "
          f"empty {len(empty_fields)}  bad {len(bad_choices) + len(bad_numbers)}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
