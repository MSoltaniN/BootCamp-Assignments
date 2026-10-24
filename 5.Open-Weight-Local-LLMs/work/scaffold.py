"""Create the per-section workspace tree for Day5 and per-section question checklists.

The question text is parsed from the official ASSIGNMENT.md so the checklists are
faithful to the assignment (no paraphrasing, no invented wording).

Layout created:

  5.Open-Weight-Local-LLMs/
    docs/                     (hand written; only missing files are noted)
    sections/sectionNN_slug/
        README.md             question checklist + artifacts + notes slot
        answers.md            filled later (created empty with headers)
        src/                  code for that section
        out/                  artifacts produced by that section
    Day5_Run_Output/          flat artifact root expected by check_submission.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assignment" / "source" / "Day5"
ASSIGNMENT = SRC / "ASSIGNMENT.md"

# section number -> (slug, kind, artifacts owner)
SECTIONS = {
    1: ("section01_license_provenance", "conceptual", []),
    2: ("section02_architecture_memory", "conceptual", []),
    3: ("section03_engine_infrastructure", "conceptual", []),
    4: ("section04_eval_tuning_security", "conceptual", []),
    5: (
        "section05_catalog_audit",
        "practical",
        ["model_catalog_clean.csv", "acceptance_plan.json", "provenance.json"],
    ),
    6: (
        "section06_capacity_cost",
        "practical",
        ["capacity_recommendation.json", "capacity_matrix.csv"],
    ),
    7: (
        "section07_quantization_gguf",
        "practical",
        ["quantization_selection.json", "quant_test_predictions.npy", "quantization_report.json"],
    ),
    8: (
        "section08_tokenizer_local_llm",
        "practical",
        ["runtime_config.json", "tokenizer_report.json"],
    ),
    9: (
        "section09_quant_eval",
        "practical",
        ["selection.json", "test_predictions.jsonl", "evaluation_report.json", "error_audit.csv"],
    ),
    10: (
        "section10_serving_kv",
        "practical",
        ["serving_report.json", "serving_metrics.csv"],
    ),
    11: (
        "section11_adapter",
        "practical",
        [
            "selected_adapter.npz",
            "adapter_selection.json",
            "adapter_test_predictions.npy",
            "adapter_base_test_predictions.npy",
            "adapter_report.json",
        ],
    ),
    12: (
        "section12_hr_workflow",
        "practical",
        [
            "local_agent.sqlite",
            "agent_trace.json",
            "security_tests.json",
            "handoff_manifest.json",
            "release_card.md",
        ],
    ),
}

HEADER_RE = re.compile(r"^## بخش (\d+): (.+?) \((\d+(?:\.\d+)?) نمره\)\s*$")
Q_RE = re.compile(r"^### زیرسؤال (\d+\.\d+) \((\d+(?:\.\d+)?) نمره\)\s*$")


def parse() -> list[dict]:
    lines = ASSIGNMENT.read_text(encoding="utf-8").splitlines()
    sections: list[dict] = []
    sec = None
    q = None
    intro: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        m = HEADER_RE.match(line)
        if m:
            sec = {
                "no": int(m.group(1)),
                "title": m.group(2).strip(),
                "points": float(m.group(3)),
                "intro": [],
                "questions": [],
            }
            sections.append(sec)
            intro = sec["intro"]
            q = None
            continue
        m = Q_RE.match(line)
        if m and sec is not None:
            q = {
                "id": m.group(1),
                "points": float(m.group(2)),
                "prompt": "",
                "options": [],
                "fields": [],
            }
            sec["questions"].append(q)
            intro = []
            continue
        if line.startswith("#"):
            continue
        if q is not None:
            if line.startswith("- "):
                body = line[2:].strip()
                if body.startswith("گزینهٔ منتخب:"):
                    opts = body.split(":", 1)[1].strip()
                    q["options"] = [o.strip() for o in opts.split(" / ") if o.strip()]
                elif body == "روش اجرا و تحلیل":
                    continue
                else:
                    q["fields"].append(body)
            elif line.strip() and not q["prompt"]:
                q["prompt"] = line.strip()
        elif sec is not None and line.strip():
            intro.append(line.strip())
    return sections


def render_section(sec: dict) -> str:
    no = sec["no"]
    slug, kind, artifacts = SECTIONS[no]
    kind_fa = "مفهومی (گزینه + دلیل)" if kind == "conceptual" else "عملی (کد + خروجی + تحلیل)"
    out: list[str] = [
        f"# بخش {no} — {sec['title']}",
        "",
        f"- نوع: **{kind_fa}**",
        f"- نمرهٔ بخش: **{sec['points']}**",
        f"- تعداد زیرسؤال: **{len(sec['questions'])}**",
        f"- پوشهٔ کد: `sections/{slug}/src/`",
        f"- پوشهٔ خروجی: `sections/{slug}/out/`",
    ]
    if artifacts:
        out.append("- آرتیفکت‌های تحویلی (در `Day5_Run_Output/`): " + ", ".join(f"`{a}`" for a in artifacts))
    out += ["", "## متن رسمی بخش", ""]
    out += ["> " + t for t in sec["intro"]] or ["> (بدون مقدمه)"]
    out += [
        "",
        "## چک‌لیست زیرسؤال‌ها",
        "",
        "برای هر زیرسؤال: عنوان «زیرسؤال N.M»، کد انگلیسی + خروجی اجرا، و تحلیل فارسی راست‌به‌چپ.",
        "",
    ]
    for q in sec["questions"]:
        out.append(f"### زیرسؤال {q['id']} ({q['points']} نمره)")
        out.append("")
        out.append(f"- [ ] صورت سؤال: {q['prompt']}")
        if q["options"]:
            out.append("- [ ] گزینه‌های مجاز (یکی انتخاب شود):")
            for i, opt in enumerate(q["options"]):
                out.append(f"  - `{i}` {opt}")
            out.append("- [ ] دلیل انتخاب (فارسی، با ارجاع به شواهد)")
        else:
            if q["fields"]:
                out.append("- [ ] فیلدهای پاسخ:")
                for f in q["fields"]:
                    out.append(f"  - {f}")
            out.append("- [ ] کد اجراشده + خروجی واقعی")
            out.append("- [ ] تحلیل فارسی (روش، تصمیم، محدودیت)")
        out.append("")
    return "\n".join(out)


def render_answers_stub(sec: dict) -> str:
    out = [f"# پاسخ‌های بخش {sec['no']} — {sec['title']}", ""]
    out.append("> این فایل با پاسخ‌های نهایی پر می‌شود. هر پاسخ باید شامل گزینه/فیلد و دلیل باشد.")
    out.append("")
    for q in sec["questions"]:
        out.append(f"## {q['id']}")
        out.append("")
        out.append(f"**سؤال:** {q['prompt']}")
        out.append("")
        if q["options"]:
            out.append("**گزینهٔ منتخب:** ")
            out.append("")
            out.append("**دلیل:** ")
        else:
            for f in q["fields"]:
                out.append(f"**{f}:** ")
                out.append("")
            out.append("**روش اجرا و تحلیل:** ")
        out.append("")
    return "\n".join(out)


def main() -> None:
    sections = parse()
    assert len(sections) == 12, len(sections)
    total_q = sum(len(s["questions"]) for s in sections)
    assert total_q == 144, total_q

    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "Day5_Run_Output").mkdir(exist_ok=True)

    checklist: list[str] = [
        "# چک‌لیست ۱۴۴ زیرسؤال",
        "",
        "خودکار از `assignment/source/Day5/ASSIGNMENT.md` ساخته شده است (بدون تغییر متن).",
        "",
        "| بخش | عنوان | نمره | تعداد | پوشه |",
        "|---|---|---|---|---|",
    ]
    for sec in sections:
        slug, kind, _ = SECTIONS[sec["no"]]
        d = ROOT / "sections" / slug
        for sub in ("src", "out"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        (d / "README.md").write_text(render_section(sec), encoding="utf-8")
        ans = d / "answers.md"
        if not ans.exists():
            ans.write_text(render_answers_stub(sec), encoding="utf-8")
        checklist.append(
            f"| {sec['no']} | {sec['title']} | {sec['points']} | {len(sec['questions'])} | `sections/{slug}` |"
        )

    checklist += ["", f"جمع زیرسؤال: **{total_q}** | جمع نمره: **{sum(s['points'] for s in sections)}**"]
    (ROOT / "docs" / "03_question_checklist.md").write_text("\n".join(checklist), encoding="utf-8")

    print(f"sections={len(sections)} questions={total_q} points={sum(s['points'] for s in sections)}")
    for sec in sections:
        print(f"  {sec['no']:>2} {SECTIONS[sec['no']][0]:<36} {sec['points']:>5} {len(sec['questions'])}")


if __name__ == "__main__":
    main()
