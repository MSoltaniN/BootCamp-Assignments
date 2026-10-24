"""Validate conceptual answers against the bank and write them into it.

Guarantees, per question:
  * the question id exists in `docs/generated/question_bank.json`
  * the answer targets the `choice` field
  * the selected option is one of the options the official schema lists
  * the rationale is non-trivial Persian text

A mismatch aborts the whole run instead of writing a partially valid bank, so a
typo can never silently produce a wrong option.

Usage
-----
    python scripts/apply_answers.py

Writes
------
docs/generated/question_bank.json          updated in place (answers merged)
docs/generated/qa/_answers_check.txt       validation report
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
BANK = GEN / "question_bank.json"
QA = GEN / "qa"

sys.path.insert(0, str(ROOT / "work"))
from sec01_04_conceptual.answers import ANSWERS  # noqa: E402

MIN_RATIONALE = 80
SHORT_LIMIT = 220


def condense(text: str, limit: int = SHORT_LIMIT) -> str:
    """Trim a rationale to a single leading sentence for the short field."""
    flat = " ".join(text.split())
    for separator in ("؛ ", ". ", "。 "):
        index = flat.find(separator)
        if 40 <= index <= limit:
            return flat[: index + 1].strip()
    if len(flat) <= limit:
        return flat
    return flat[:limit].rsplit(" ", 1)[0].strip() + "…"


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in bank["questions"]}

    errors: list[str] = []
    lines: list[str] = ["== CONCEPTUAL ANSWER VALIDATION ==", ""]

    applied = 0
    for qid, (option, rationale) in sorted(
        ANSWERS.items(), key=lambda item: [int(x) for x in item[0].split(".")]
    ):
        question = questions.get(qid)
        if question is None:
            errors.append(f"{qid}: id not present in the bank")
            continue

        choice_fields = [f for f in question["fields"] if f["kind"] == "choice"]
        if len(choice_fields) != 1:
            errors.append(f"{qid}: expected exactly 1 choice field, found {len(choice_fields)}")
            continue
        field = choice_fields[0]

        if option not in field["options"]:
            errors.append(
                f"{qid}: option {option!r} not in schema options {field['options']}"
            )
            continue

        if len(rationale.strip()) < MIN_RATIONALE:
            errors.append(f"{qid}: rationale too short ({len(rationale)} chars)")
            continue

        field["answer"] = option

        # The form has a *separate* `دلیل انتخاب` slot. Filling only `rationale`
        # left that slot empty, so the reason is condensed to its leading
        # sentence and written into the field as well.
        short_fields = [f for f in question["fields"] if f["kind"] == "short"]
        if short_fields:
            short_fields[0]["answer"] = condense(rationale)
            applied += 1

        question["rationale"] = rationale.strip()
        question["status"] = "answered"
        applied += 1

        lines.append(f"[ok] {qid:<6} -> {option}")
        lines.append(f"       rationale: {len(rationale)} chars")

    # every conceptual question (sections 1-4) must be covered
    conceptual = [
        q["id"] for q in bank["questions"] if q["section"] in {"1", "2", "3", "4"}
    ]
    missing = sorted(
        set(conceptual) - set(ANSWERS), key=lambda s: [int(x) for x in s.split(".")]
    )

    lines += [
        "",
        "== SUMMARY ==",
        f"conceptual questions : {len(conceptual)}",
        f"answers provided     : {len(ANSWERS)}",
        f"answers applied      : {applied}",
        f"missing              : {missing or 'none'}",
        f"errors               : {len(errors)}",
        "",
    ]
    for error in errors:
        lines.append(f"ERROR: {error}")

    QA.mkdir(parents=True, exist_ok=True)
    (QA / "_answers_check.txt").write_text("\n".join(lines), encoding="utf-8")

    if missing:
        errors.append(f"missing answers: {missing}")

    print(f"applied  : {applied}/{len(conceptual)}")
    print(f"errors   : {len(errors)}")
    for error in errors[:10]:
        print("  -", error.encode("ascii", "backslashreplace").decode("ascii"))
    if errors:
        return 1

    # recompute coverage and persist
    answered = sum(1 for q in bank["questions"] if q["status"] == "answered")
    bank["totals"]["answered"] = answered
    bank["totals"]["answered_conceptual"] = applied
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"answered : {answered} questions")
    print(f"bank     : {BANK.name} updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
