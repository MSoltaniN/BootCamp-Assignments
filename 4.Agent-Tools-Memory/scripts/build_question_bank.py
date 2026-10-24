"""Merge the parsed site form with the official grading schema.

The site HTML cannot distinguish a numeric input from a free-text input, and it
does not carry the `required` flag. `Day4_Grading/question_schema.json` does.
This script produces the single source of truth used for answering:

    docs/generated/question_bank.json

Each question gains:
  * `kind`            - authoritative field kind (choice/short/number/textarea)
  * `required`        - whether the field must be filled
  * `answer`          - None until filled
  * `rationale`       - Persian analysis (40% of the mark)
  * `evidence`        - list of artifact paths / notebook cells backing the answer

It also writes `docs/generated/answer_key.md`, a Persian, RTL-friendly form
mirror that lists every slot in submission order.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
OFFICIAL = (
    ROOT / "assignment" / "source" / "Day4" / "Day4_Grading" / "question_schema.json"
)

site = json.loads((GEN / "questions.json").read_text(encoding="utf-8"))
official = json.loads(OFFICIAL.read_text(encoding="utf-8"))

# `apply_answers.py` writes answers into the bank. Rebuilding must never silently
# discard them, so any previous answers are read back and merged below.
BANK_PATH = GEN / "question_bank.json"
previous: dict[str, dict] = {}
if BANK_PATH.exists():
    try:
        old = json.loads(BANK_PATH.read_text(encoding="utf-8"))
        previous = {q["id"]: q for q in old.get("questions", [])}
    except json.JSONDecodeError:
        previous = {}

# index the official schema by question id
official_q: dict[str, dict] = {}
for section in official:
    for question in section["questions"]:
        official_q[question["id"]] = question

official_sections = {str(section["number"]): section for section in official}

COARSE = {"choice": "radio", "short": "input", "number": "input", "textarea": "textarea"}

bank_questions: list[dict] = []
warnings: list[str] = []

for question in site["questions"]:
    qid = question["id"]
    reference = official_q.get(qid)
    if reference is None:
        warnings.append(f"{qid}: not found in official schema")
        continue

    ref_fields = reference["fields"]
    my_fields = question["fields"]
    if len(ref_fields) != len(my_fields):
        warnings.append(
            f"{qid}: field count {len(my_fields)} (site) vs {len(ref_fields)} (schema)"
        )

    fields: list[dict] = []
    for index, ref_field in enumerate(ref_fields):
        mine = my_fields[index] if index < len(my_fields) else {}
        kind = ref_field["kind"]
        # sanity: the coarse shape must agree, otherwise the alignment is off
        if mine and COARSE.get(kind) != mine["kind"]:
            warnings.append(
                f"{qid}: field[{index}] shape {mine['kind']} vs schema {kind}"
            )
        fields.append(
            {
                "index": index,
                "field_id": mine.get("id", f"{qid}-{index}"),
                "label": ref_field["label"],
                "kind": kind,
                "options": ref_field.get("options", []),
                "required": ref_field.get("required", True),
                "answer": None,
            }
        )

    # carry forward anything already answered
    carried = previous.get(qid, {})
    if carried.get("status") == "answered":
        old_fields = {f["index"]: f for f in carried.get("fields", [])}
        for field in fields:
            saved = old_fields.get(field["index"])
            if saved and saved.get("answer") is not None:
                field["answer"] = saved["answer"]

    bank_questions.append(
        {
            "id": qid,
            "section": question["section"],
            "points": float(reference["score"]),
            "type": question["type"],
            "prompt": reference["prompt"],
            "fields": fields,
            "rationale": carried.get("rationale"),
            "evidence": carried.get("evidence", []),
            "status": carried.get("status", "todo"),
        }
    )

# section metadata, keeping the site's intro text but the schema's score
bank_sections: list[dict] = []
for section in site["sections"]:
    number = section["number"]
    ref = official_sections.get(number, {})
    group = [q for q in bank_questions if q["section"] == number]
    bank_sections.append(
        {
            "number": number,
            "title": ref.get("title", section["title"]),
            "dataset": ref.get("dataset", section["meta"]),
            "intro": ref.get("intro", section["intro"]),
            "points": float(ref.get("score", sum(q["points"] for q in group))),
            "question_count": len(group),
        }
    )

totals = {
    "sections": len(bank_sections),
    "questions": len(bank_questions),
    "answered": sum(1 for q in bank_questions if q["status"] == "answered"),
    "points": sum(q["points"] for q in bank_questions),
    "choice_fields": sum(
        1 for q in bank_questions for f in q["fields"] if f["kind"] == "choice"
    ),
    "short_fields": sum(
        1 for q in bank_questions for f in q["fields"] if f["kind"] == "short"
    ),
    "number_fields": sum(
        1 for q in bank_questions for f in q["fields"] if f["kind"] == "number"
    ),
    "textarea_fields": sum(
        1 for q in bank_questions for f in q["fields"] if f["kind"] == "textarea"
    ),
}

bank = {
    "assignment": "DataMining_Bootcamp_Day4_Assignment",
    "schema_version": "2.1",
    "revision": "2026-10-16-r2",
    "title": site["title"],
    "student_pack": site["student_pack"],
    "source_page": site["source_page"],
    "totals": totals,
    "sections": bank_sections,
    "questions": bank_questions,
    "warnings": warnings,
}

(GEN / "question_bank.json").write_text(
    json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8"
)

# ---------------------------------------------------------------------------
# Persian answer key mirror
# ---------------------------------------------------------------------------
KIND_FA = {
    "choice": "گزینه",
    "short": "پاسخ کوتاه",
    "number": "عدد",
    "textarea": "متن بلند (کد + خروجی + تحلیل)",
}

lines: list[str] = [
    "# کلید پاسخ — تکلیف ۴",
    "",
    f"مجموع: **{totals['points']:g} نمره** · "
    f"**{totals['questions']}** زیرسؤال · **{totals['sections']}** بخش",
    "",
    "| نوع فیلد | تعداد |",
    "|---|---|",
    f"| گزینه‌ای | {totals['choice_fields']} |",
    f"| پاسخ کوتاه | {totals['short_fields']} |",
    f"| عددی | {totals['number_fields']} |",
    f"| متن بلند | {totals['textarea_fields']} |",
    "",
    "> قاعدهٔ نمره: مفهومی ۶۰٪ گزینه + ۴۰٪ دلیل؛ عملی ۶۰٪ روش/کد/خروجی + ۴۰٪ تحلیل.",
    "",
]

for section in bank_sections:
    number = section["number"]
    group = [q for q in bank_questions if q["section"] == number]
    lines += [
        "---",
        "",
        f"## بخش {number} — {section['title']} ({section['points']:g} نمره)",
        "",
        f"**داده:** `{section['dataset']}`",
        "",
        f"> {section['intro']}",
        "",
    ]
    for question in group:
        lines += [
            f"### زیرسؤال {question['id']} — {question['points']:g} نمره",
            "",
            question["prompt"],
            "",
        ]
        # The 40% analysis already has a dedicated slot on operational questions
        # (the "روش اجرا و تحلیل" textarea) and on conceptual ones (the "دلیل
        # انتخاب" field). Only add a separate prompt when neither exists.
        has_analysis_slot = any(
            field["kind"] == "textarea"
            or "دلیل" in field["label"]
            for field in question["fields"]
        )
        for field in question["fields"]:
            label = field["label"]
            marker = "" if field["required"] else " _(اختیاری)_"
            if field["kind"] == "choice":
                opts = " · ".join(field["options"])
                lines.append(f"- **{label}**{marker} — {opts}")
                lines.append("  - پاسخ: `……`")
            elif field["kind"] == "number":
                lines.append(f"- **{label}**{marker} — عدد")
                lines.append("  - پاسخ: `……`")
            elif field["kind"] == "short":
                lines.append(f"- **{label}**{marker} — پاسخ کوتاه")
                lines.append("  - پاسخ: `……`")
            else:
                lines.append(f"- **{label}**{marker} — {KIND_FA['textarea']}")
                lines.append("  - پاسخ: ……")
        if not has_analysis_slot:
            lines.append("- **تحلیل (۴۰٪):** ……")
        lines.append("")

(GEN / "answer_key.md").write_text("\n".join(lines), encoding="utf-8")

print(f"questions : {totals['questions']}")
print(f"points    : {totals['points']:g}")
print(f"fields    : choice={totals['choice_fields']} short={totals['short_fields']} "
      f"number={totals['number_fields']} textarea={totals['textarea_fields']}")
print(f"warnings  : {len(warnings)}")
for warning in warnings[:20]:
    print("  -", warning.encode("ascii", "backslashreplace").decode("ascii"))
