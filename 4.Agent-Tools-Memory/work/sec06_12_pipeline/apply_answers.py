"""Validate the per-section answer files and re-apply them to the bank.

Aggregates FIELD_ANSWERS and RATIONALE from the seven section folders, checks
each value against the question bank, writes the answers in, then re-renders the
submission sheet. Exits non-zero on any failure.

Run:
    .venv\\Scripts\\python.exe work/sec06_12_pipeline/apply_answers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work"))

from sec06_mcp.answers import FIELD_ANSWERS as F6, RATIONALE as R6  # noqa: E402
from sec07_loop.answers import FIELD_ANSWERS as F7, RATIONALE as R7  # noqa: E402
from sec08_memory.answers import FIELD_ANSWERS as F8, RATIONALE as R8  # noqa: E402
from sec09_router.answers import FIELD_ANSWERS as F9, RATIONALE as R9  # noqa: E402
from sec10_security.answers import FIELD_ANSWERS as F10, RATIONALE as R10  # noqa: E402
from sec11_eval.answers import FIELD_ANSWERS as F11, RATIONALE as R11  # noqa: E402
from sec12_rollout.answers import FIELD_ANSWERS as F12, RATIONALE as R12  # noqa: E402

GEN = ROOT / "docs" / "generated"
BANK = GEN / "question_bank.json"
QA = GEN / "qa"
ANALYSIS_LABEL = "روش اجرا و تحلیل"
SECTIONS = {"6", "7", "8", "9", "10", "11", "12"}
MIN_RATIONALE = 200

FIELD_ANSWERS: dict[tuple[str, int], object] = {}
RATIONALE: dict[str, str] = {}
for fields, rationales in (
    (F6, R6), (F7, R7), (F8, R8), (F9, R9),
    (F10, R10), (F11, R11), (F12, R12),
):
    FIELD_ANSWERS.update(fields)
    RATIONALE.update(rationales)


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in bank["questions"]}
    target = [q for q in bank["questions"] if q["section"] in SECTIONS]

    lines = ["== SECTIONS 6-12 VALIDATION ==", ""]
    errors: list[str] = []

    for question in target:
        qid = question["id"]
        if qid not in RATIONALE:
            errors.append(f"{qid}: no rationale")
            continue
        if len(RATIONALE[qid].strip()) < MIN_RATIONALE:
            errors.append(f"{qid}: rationale too short ({len(RATIONALE[qid])})")
            continue

        applied = 0
        for index, field in enumerate(question["fields"]):
            if field["label"] == ANALYSIS_LABEL:
                field["answer"] = RATIONALE[qid].strip()
                applied += 1
                continue

            key = (qid, index)
            if key not in FIELD_ANSWERS:
                errors.append(f"{qid}: field[{index}] {field['label']!r} unanswered")
                continue

            value = FIELD_ANSWERS[key]
            if field["kind"] == "number":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"{qid}: field[{index}] expects number, got {value!r}")
                    continue
            elif field["kind"] == "choice":
                if value not in field["options"]:
                    errors.append(
                        f"{qid}: field[{index}] {value!r} not in {field['options']}"
                    )
                    continue
            else:
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{qid}: field[{index}] empty text")
                    continue

            field["answer"] = value
            applied += 1

        question["rationale"] = RATIONALE[qid].strip()
        if applied == len(question["fields"]):
            question["status"] = "answered"
            lines.append(f"[ok] {qid:<6} {applied}/{len(question['fields'])}")
        else:
            lines.append(f"[!!] {qid:<6} {applied}/{len(question['fields'])}")

    for qid, index in FIELD_ANSWERS:
        question = questions.get(qid)
        if question is None:
            errors.append(f"{qid}: unknown question")
        elif index >= len(question["fields"]):
            errors.append(f"{qid}: index {index} out of range")

    answered = [q for q in target if q["status"] == "answered"]
    points = sum(q["points"] for q in answered)

    lines += ["", "== SUMMARY ==",
              f"target    : {len(target)}",
              f"answered  : {len(answered)}",
              f"points    : {points:g}/68",
              f"fields    : {len(FIELD_ANSWERS)}",
              f"rationales: {len(RATIONALE)}",
              f"errors    : {len(errors)}", ""]
    lines += [f"ERROR: {e}" for e in errors]

    QA.mkdir(parents=True, exist_ok=True)
    (QA / "_sections_6_12_check.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"answered {len(answered)}/{len(target)}  points {points:g}/68  errors {len(errors)}")
    if errors:
        for error in errors[:15]:
            print("  -", error.encode("ascii", "backslashreplace").decode("ascii"))
        return 1

    total = sum(1 for q in bank["questions"] if q["status"] == "answered")
    bank["totals"]["answered"] = total
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")

    render(target)
    print(f"bank {total} answered overall")
    return 0


def render(target: list[dict]) -> None:
    md = ["# برگهٔ ارسال — بخش‌های ۶ تا ۱۲", "",
          "پاسخ‌ها از اجرای واقعی `work/sec06_12_pipeline/run_all.py` آمده‌اند. "
          "خروجی خام در `Day4_Run_Output/sections_6_12.json` است.", ""]
    for section in ["6", "7", "8", "9", "10", "11", "12"]:
        group = [q for q in target if q["section"] == section]
        if not group:
            continue
        md += ["---", "", f"## بخش {section}", ""]
        for question in group:
            md += [f"### {question['id']} — {question['points']:g} نمره", "",
                   f"**سؤال:** {question['prompt']}", ""]
            for field in question["fields"]:
                answer = field["answer"] if field["answer"] is not None else "……"
                md.append(f"- **{field['label']}:** {answer}")
            md.append("")
    (GEN / "submission_6_12.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
