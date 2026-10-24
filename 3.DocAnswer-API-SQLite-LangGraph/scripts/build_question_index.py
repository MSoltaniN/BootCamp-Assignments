"""Build a tracked index of all 144 sub-questions from the assignment text.

Reads `assignment/assignment_text.txt` (the text extracted from the saved iCourse
page) and writes:

  * `artifacts/questions.json`            – machine-readable index (for notebook scaffolding)
  * `docs/03_question_checklist.md`       – the human tracking table

The script asserts the score arithmetic (144 questions, 48 conceptual + 96
practical, 24 + 76 = 100 points) so a silent parsing drift cannot slip through.

    python scripts/build_question_index.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = ROOT / "assignment" / "assignment_text.txt"
JSON_OUT = ROOT / "artifacts" / "questions.json"
MD_OUT = ROOT / "docs" / "03_question_checklist.md"

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

SECTIONS = [
    (1, "معماری محصول و انتخاب مرحلهٔ توسعه", "بدون دیتاست (سناریوهای مفهومی)", 6),
    (2, "قرارداد API و رفتار هنگام خطا", "بدون دیتاست (سناریوهای مفهومی)", 6),
    (3, "هویت و حاکمیت داده", "بدون دیتاست (سناریوهای مفهومی)", 6),
    (4, "استدلال دربارهٔ RAG و ارزیابی", "بدون دیتاست (سناریوهای مفهومی)", 6),
    (5, "کلاینت API و قرارداد خطا", "datasets/04_API", 8),
    (6, "دیتابیس SQLite و قیود داده", "datasets/03_Application + day3.sqlite", 8),
    (7, "ورود اسناد و حفظ منشأ", "datasets/01_Corpus + 03_Application/policies.jsonl", 10),
    (8, "بردارسازی و بازیابی چندمسیره", "datasets/01_Corpus + resources/embedding_model", 12),
    (9, "ارزیابی بازیابی و کنترل نشت آزمون", "datasets/02_Evaluation (gold test نزد مدرس)", 10),
    (10, "انتخاب مدل و ساخت مسیریاب عصبی", "datasets/05_Router/requests.csv", 10),
    (11, "گردش کار LangGraph و پاسخ مستند", "01_Corpus + 03_Application + 06_Robustness", 10),
    (12, "یکپارچه‌سازی و آمادگی تحویل", "همهٔ دیتاست‌ها + day3.sqlite", 8),
]

# Where the reproduceable output of each section lives once it is built.
SECTION_OUTPUT = {
    1: "docs/07_conceptual_answers.md",
    2: "docs/07_conceptual_answers.md",
    3: "docs/07_conceptual_answers.md",
    4: "docs/07_conceptual_answers.md",
    5: "work/sec05_api_client/",
    6: "work/sec06_sqlite/ + day3.sqlite",
    7: "work/sec07_ingestion/artifacts/",
    8: "work/sec08_embeddings/",
    9: "work/sec09_evaluation/ + deliverables/",
    10: "work/sec10_router/",
    11: "work/sec11_langgraph/",
    12: "work/sec12_integration/",
}

# [0-9] rather than \d on purpose: \d also matches Persian digits, which would
# turn "1.1۰٫۵" into section 1 / number 10.
HEAD_RE = re.compile(r"^([0-9]{1,2})\.([0-9]{1,2})\s*([۰-۹0-9٫.]+)\s*نمره\s*$")


def to_float(token: str) -> float:
    t = token.translate(PERSIAN_DIGITS).replace("٫", ".")
    return float(t)


def fa_num(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def parse() -> list[dict]:
    lines = [ln.strip() for ln in TEXT.read_text(encoding="utf-8").splitlines()]
    items = []
    for i, line in enumerate(lines):
        m = HEAD_RE.match(line)
        if not m:
            continue
        section, number = int(m.group(1)), int(m.group(2))
        if not 1 <= section <= 12 or not 1 <= number <= 12:
            continue
        text = ""
        for nxt in lines[i + 1: i + 4]:
            if nxt and not nxt.startswith(("گزینهٔ منتخب", "دلیل انتخاب", "پیوست:", "روش اجرا")):
                text = nxt
                break
        items.append({
            "section": section,
            "number": number,
            "id": f"{section}.{number}",
            "points": to_float(m.group(3)),
            "kind": "مفهومی" if section <= 4 else "عملی",
            "question": text,
            "answer_kind": "گزینه + دلیل" if section <= 4 else "عدد/گزینه + روش اجرا و تحلیل",
        })
    return items


def main() -> int:
    items = parse()
    by_section: dict[int, list[dict]] = {}
    for it in items:
        by_section.setdefault(it["section"], []).append(it)

    # --- integrity checks -------------------------------------------------
    problems = []
    if len(items) != 144:
        problems.append(f"expected 144 sub-questions, parsed {len(items)}")
    for sec, title, _, points in SECTIONS:
        got = by_section.get(sec, [])
        if len(got) != 12:
            problems.append(f"section {sec}: expected 12 sub-questions, got {len(got)}")
        total = round(sum(q["points"] for q in got), 2)
        if abs(total - points) > 1e-9:
            problems.append(f"section {sec}: points sum {total} != declared {points}")
        if any(q["question"] == "" for q in got):
            problems.append(f"section {sec}: empty question text for "
                            + ", ".join(q["id"] for q in got if not q["question"]))
    conceptual = [q for q in items if q["kind"] == "مفهومی"]
    practical = [q for q in items if q["kind"] == "عملی"]
    if len(conceptual) != 48 or len(practical) != 96:
        problems.append(f"expected 48 conceptual / 96 practical, got {len(conceptual)} / {len(practical)}")
    grand = round(sum(q["points"] for q in items), 2)
    if abs(grand - 100) > 1e-9:
        problems.append(f"total points {grand} != 100")

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(
        {"total": len(items), "total_points": grand, "sections": [
            {"section": s, "title": t, "dataset": d, "points": p,
             "questions": by_section.get(s, [])} for s, t, d, p in SECTIONS]},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # --- markdown checklist ----------------------------------------------
    md = [
        "# چک‌لیست ۱۴۴ زیرسؤال — تکلیف ۳",
        "",
        "این جدول از متن تکلیف ساخته شده و منبع حقیقت برای پیشرفت کار است.",
        "`☐` انجام‌نشده، `◐` در جریان، `☑` انجام‌شده و عددش در سایت ثبت شده.",
        "",
        f"- کل زیرسؤال: **{len(items)}** ({len(conceptual)} مفهومی + {len(practical)} عملی)",
        f"- کل نمره: **{grand:g}** از ۱۰۰",
        "- قاعدهٔ سخت: عددی که در سایت می‌نویسی باید همان باشد که خروجی نوت‌بوک چاپ می‌کند.",
        "",
    ]
    status_legend = "| # | زیرسؤال | نمره | نوع | وضعیت |"
    for sec, title, dataset, points in SECTIONS:
        rows = by_section.get(sec, [])
        md += [
            f"## بخش {fa_num(sec)} — {title}",
            "",
            f"- نمرهٔ بخش: **{points}** ({len(rows)} زیرسؤال)",
            f"- داده: `{dataset}`",
            f"- محل خروجی: `{SECTION_OUTPUT[sec]}`",
            "",
            status_legend,
            "|---|---|---|---|---|",
        ]
        for q in rows:
            text = q["question"].replace("|", "\\|")
            if len(text) > 130:
                text = text[:127].rstrip() + "…"
            md.append(f"| {q['id']} | {text} | {q['points']:g} | {q['kind']} | ☐ |")
        md.append("")
    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"parsed {len(items)} sub-questions, total {grand:g} points")
    print(f"written: {JSON_OUT}")
    print(f"written: {MD_OUT}")
    if problems:
        print("\nINTEGRITY PROBLEMS:")
        for p in problems:
            print(" -", p)
        return 1
    print("integrity: OK (144 = 48 + 96, 100 points, 12 sections x 12)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
