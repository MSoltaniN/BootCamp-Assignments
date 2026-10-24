"""Render the answered questions as a submission sheet.

Produces two files:

    docs/generated/submission_conceptual.md   Persian, ready to copy into the form
    docs/generated/submission_conceptual.txt  same content, plain text

Only questions with `status == "answered"` are included, so the sheet always
reflects the bank rather than a hand-maintained list.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
BANK = GEN / "question_bank.json"


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    sections = {s["number"]: s for s in bank["sections"]}

    answered = [q for q in bank["questions"] if q["status"] == "answered"]
    by_section: dict[str, list[dict]] = {}
    for question in answered:
        by_section.setdefault(question["section"], []).append(question)

    md: list[str] = [
        "# برگهٔ ارسال پاسخ — بخش‌های ۱ تا ۴",
        "",
        f"پاسخ‌داده‌شده: **{len(answered)}** زیرسؤال از ۱۴۴",
        "",
        "> هر پاسخ دو بخش دارد: مقدار فیلد (گزینه) و دلیل. گزینه را از فهرست فرم انتخاب کن و دلیل را در فیلد «دلیل انتخاب» بگذار.",
        "",
    ]
    txt: list[str] = [
        "SUBMISSION - SECTIONS 1-4",
        f"answered: {len(answered)}",
        "",
    ]

    for number in ["1", "2", "3", "4"]:
        group = by_section.get(number, [])
        if not group:
            continue
        section = sections.get(number, {})
        md += [
            "---",
            "",
            f"## بخش {number} — {section.get('title', '')}",
            "",
        ]
        txt += ["=" * 60, f"SECTION {number}", "=" * 60]

        for question in group:
            choice = next(
                (f for f in question["fields"] if f["kind"] == "choice"), None
            )
            selected = choice["answer"] if choice else None
            md += [
                f"### {question['id']}",
                "",
                f"**سؤال:** {question['prompt']}",
                "",
                f"**پاسخ:** `{selected}`",
                "",
                f"**دلیل انتخاب:** {question['rationale']}",
                "",
            ]
            txt += [
                f"--- {question['id']}",
                f"ANSWER : {selected}",
                f"REASON : {question['rationale']}",
                "",
            ]

    (GEN / "submission_conceptual.md").write_text("\n".join(md), encoding="utf-8")
    (GEN / "submission_conceptual.txt").write_text("\n".join(txt), encoding="utf-8")

    print(f"answered: {len(answered)}")
    print(f"written : submission_conceptual.md / .txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
