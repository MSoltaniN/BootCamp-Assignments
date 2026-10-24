"""Validate and merge section-5 answers into the question bank plus a report.

Checks, per field:
  * the field exists at the stated index
  * a number field gets a real number
  * a choice field gets one of that field's own option strings
  * the "روش اجرا و تحلیل" textarea gets the rationale

Any failure aborts before writing, so the bank can never hold a half-valid answer.

Usage
-----
    .venv\\Scripts\\python.exe work/sec05_data/apply_section5.py

Outputs
-------
docs/generated/question_bank.json        answers merged
docs/generated/qa/_section5_check.txt    validation report
docs/generated/submission_section5.md    Persian submission sheet
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work"))

from sec05_data.answers import FIELD_ANSWERS, RATIONALE  # noqa: E402

GEN = ROOT / "docs" / "generated"
BANK = GEN / "question_bank.json"
QA = GEN / "qa"

ANALYSIS_LABEL = "روش اجرا و تحلیل"
MIN_RATIONALE = 200


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in bank["questions"]}
    section5 = [q for q in bank["questions"] if q["section"] == "5"]

    lines = ["== SECTION 5 ANSWER VALIDATION ==", ""]
    errors: list[str] = []

    for question in section5:
        qid = question["id"]
        if qid not in RATIONALE:
            errors.append(f"{qid}: no rationale")
            continue
        if len(RATIONALE[qid].strip()) < MIN_RATIONALE:
            errors.append(f"{qid}: rationale too short ({len(RATIONALE[qid])} chars)")
            continue

        fields = question["fields"]
        applied = 0
        for index, field in enumerate(fields):
            if field["label"] == ANALYSIS_LABEL:
                field["answer"] = RATIONALE[qid]
                applied += 1
                continue

            key = (qid, index)
            if key not in FIELD_ANSWERS:
                # fields without an explicit answer must at least be documented
                errors.append(f"{qid}: field[{index}] {field['label']!r} has no answer")
                continue

            value = FIELD_ANSWERS[key]
            if field["kind"] == "number":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"{qid}: field[{index}] expects a number, got {value!r}")
                    continue
            elif field["kind"] == "choice":
                if value not in field["options"]:
                    errors.append(
                        f"{qid}: field[{index}] option {value!r} not in {field['options']}"
                    )
                    continue
            elif field["kind"] == "short":
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{qid}: field[{index}] short text empty")
                    continue
            else:  # textarea that is not the analysis slot
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{qid}: field[{index}] text empty")
                    continue

            field["answer"] = value
            applied += 1

        question["rationale"] = RATIONALE[qid]
        if applied == len(fields):
            question["status"] = "answered"
            lines.append(f"[ok] {qid:<5} fields={len(fields)} all answered")
        else:
            lines.append(f"[!!] {qid:<5} {applied}/{len(fields)} answered")

    # every provided key must reference a real field
    for qid, index in FIELD_ANSWERS:
        question = questions.get(qid)
        if question is None:
            errors.append(f"{qid}: unknown question")
        elif index >= len(question["fields"]):
            errors.append(f"{qid}: field index {index} out of range "
                          f"({len(question['fields'])} fields)")

    answered = [q for q in section5 if q["status"] == "answered"]
    points = sum(q["points"] for q in answered)

    lines += [
        "",
        "== SUMMARY ==",
        f"section 5 questions : {len(section5)}",
        f"fully answered      : {len(answered)}",
        f"points              : {points:g}/8",
        f"field answers       : {len(FIELD_ANSWERS)}",
        f"rationales          : {len(RATIONALE)}",
        f"errors              : {len(errors)}",
        "",
    ]
    for error in errors:
        lines.append(f"ERROR: {error}")

    QA.mkdir(parents=True, exist_ok=True)
    (QA / "_section5_check.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"answered: {len(answered)}/{len(section5)}  points={points:g}/8")
    print(f"errors  : {len(errors)}")
    for error in errors[:12]:
        print("  -", error.encode("ascii", "backslashreplace").decode("ascii"))
    if errors:
        return 1

    total_answered = sum(1 for q in bank["questions"] if q["status"] == "answered")
    bank["totals"]["answered"] = total_answered
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")

    write_submission(section5)
    print(f"bank    : {total_answered} answered overall")
    return 0


def write_submission(section5: list[dict]) -> None:
    """Persian sheet mirroring the form, so answers can be copied field by field."""
    md = [
        "# برگهٔ ارسال — بخش ۵ (آماده‌سازی داده و مهندسی context)",
        "",
        "پاسخ‌ها از اجرای واقعی `work/sec05_data/run_section5.py` آمده‌اند. "
        "خروجی خام در `Day4_Run_Output/section5.json` است.",
        "",
    ]
    for question in section5:
        md += [f"## {question['id']} — {question['points']:g} نمره", "",
               f"**سؤال:** {question['prompt']}", ""]
        for field in question["fields"]:
            answer = field["answer"]
            if answer is None:
                answer = "……"
            md.append(f"- **{field['label']}:** {answer}")
        md.append("")

    (GEN / "submission_section5.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
