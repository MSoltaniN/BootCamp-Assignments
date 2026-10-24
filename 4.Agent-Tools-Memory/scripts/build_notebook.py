"""Build the executed submission notebook from Student_Template.ipynb.

The template is a strict 3-cell block per sub-question:

    markdown  "### زیرسؤال N.M" + the prompt
    code      "# Write your implementation here."
    markdown  "<div dir=\"rtl\">روش اجرا و تحلیل خود را اینجا بنویسید.</div>"

This builder keeps the heading cells untouched, replaces every code cell with
real evidence code bound to the matching result key, and replaces every
analysis cell with the Persian analysis of that question. It also proves the
heading order matches the bank order before writing anything, so a shifted
template fails loudly instead of silently putting an answer under the wrong
question.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assignment" / "source" / "Day4" / "Day4_Starter" / "Student_Template.ipynb"
BANK = ROOT / "docs" / "generated" / "question_bank.json"
OUT = ROOT / "deliverables" / "notebook" / "Day4_Submission.ipynb"

CODE_PLACEHOLDER = "# Write your implementation here."
ANALYSIS_PLACEHOLDER = "روش اجرا و تحلیل خود را اینجا بنویسید."

# ---------------------------------------------------------------------------
# Evidence code. Every snippet prints real values from the run output.
# ---------------------------------------------------------------------------

PREAMBLE = '''# Setup: resolve the project root and load the run outputs once.
# The notebook lives in deliverables/notebook/, but it is run from the project
# root so that `Day4_Code` and `work` import exactly as the scripts do.
import json, sys, itertools
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "Day4_Code").is_dir())
for extra in (ROOT / "work", ROOT / "Day4_Code"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

OUT = ROOT / "Day4_Run_Output"
S5 = json.loads((OUT / "section5.json").read_text(encoding="utf-8"))
S = json.loads((OUT / "sections_6_12.json").read_text(encoding="utf-8"))
BANK = json.loads((ROOT / "docs" / "generated" / "question_bank.json").read_text(encoding="utf-8"))
BY_ID = {q["id"]: q for q in BANK["questions"]}


def show(label, value):
    """Print one piece of evidence without hiding any field."""
    print(f"{label}:")
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


print("project root:", ROOT)
print("sections 6-12 generated at:", S["generated_at"])
'''

SECTION5_NAMES = {
    1: "q5_1_inventory", 2: "q5_2_scope", 3: "q5_3_budget", 4: "q5_4_control",
    5: "q5_5_retrieval", 6: "q5_6_redaction", 7: "q5_7_dedupe",
    8: "q5_8_compression", 9: "q5_9_specialists", 10: "q5_10_profile",
    11: "q5_11_tamper", 12: "q5_12_coverage",
}

SECTION_MAP = {
    6: {
        1: ('S6["required_fields"]', 'S6["additional_properties_blocked"]'),
        2: ('S6["dispatcher"]',),
        3: ('S6["invalid_inputs"]',),
        4: ('S6["cross_scope"]',),
        5: ('S6["mcp"]["tools"]', 'S6["mcp"]["transport"]', 'S6["mcp"]["resources"]', 'S6["mcp"]["prompts"]'),
        6: ('S6["mcp"]',),
        7: ('S6["mcp"]["probe_tenant_rejected"]', 'S6["mcp"]["probe_enum_rejected"]'),
        8: ('S6["error_shape"]',),
        9: ('S6["model_outputs"]',),
        10: ('S6["fingerprint"]',),
        11: ('S6["decision_model"]',),
        12: ('S6["attachment"]',),
    },
    7: {
        1: ('S7["action_union"]',), 2: ('S7["normal_run"]',), 3: ('S7["repetition"]',),
        4: ('S7["step_cap"]',), 5: ('S7["budget"]',), 6: ('S7["deadline"]',),
        7: ('S7["retry"]',), 8: ('S7["retry_401"]',), 9: ('S7["malicious"]',),
        10: ('S7["final_scope"]',), 11: ('S7["trajectory"]',), 12: ('S7["acceptance"]',),
    },
    8: {
        1: ('S8["bootstrap"]',), 2: ('S8["ttl"]',), 3: ('S8["durability"]',),
        4: ('S8["memory_poisoning"]',), 5: ('S8["tenant_isolation"]',),
        6: ('S8["candidates"]',), 7: ('S8["final"]',), 8: ('S8["interrupt"]',),
        9: ('S8["resume"]',), 10: ('S8["replay"]',),
        11: ('S8["approval_binding"]',), 12: ('S8["rejection"]',),
    },
    9: {
        1: ('S9["labels"]',), 2: ('S9["baseline"]',), 3: ('S9["selection"]',),
        4: ('S9["threshold"]',), 5: ('S9["chaining"]',), 6: ('S9["parallel"]',),
        7: ('S9["coordinator"]',), 8: ('S9["evaluator"]',), 9: ('S9["hmac"]',),
        10: ('S9["maker_checker"]',), 11: ('S9["handoff"]',), 12: ('S9["timing"]',),
    },
    11: {
        1: ('S11["paired"]',), 2: ('S11["dev_rates"]',), 3: ('S11["predictions"]',),
        4: ('S11["bootstrap"]',), 5: ('S11["wall"]',), 6: ('S11["cost"]',),
        7: ('S11["tool_accuracy"]',), 8: ('S11["dev_rates"]',), 9: ('S11["dev_rates"]',),
        10: ('S11["audit_groups"]',), 11: ('S11["js"]',), 12: ('S11["log_quality"]',),
    },
    12: {
        1: ('S12["gate"]',), 2: ('S12["canary"]',), 3: ('S12["shadow"]',),
        4: ('S12["jobs"]',), 5: ('S12["practical_answers"]',), 6: ('S12["data_integrity"]',),
        7: ('S12["agent_card"]',), 8: ('S12["manifest"]',), 9: ('S12["weights"]',),
        10: ('S12["execution_scope"]',), 11: ('S12["incident"]',),
        12: ('S12["security_controls"]', 'S12["practical_answers"]', 'S12["test_predictions"]'),
    },
}

FAMILY = {
    3: "goal_hijack", 4: "tool_misuse", 5: "privilege_abuse", 6: "supply_chain",
    7: "code_execution", 8: "memory_poisoning", 9: "forged_message",
    10: "cascading_failure", 11: "approval_deception", 12: "rogue_agent",
}


def conceptual_code(qid: str) -> str:
    """Sections 1-4: print the prompt, verify the option, and quote the slide."""
    return f'''# اين بخش مفهومي است؛ كد اجرايي ندارد. اعتبار گزينه و منبع اسلايد را نشان مي‌دهيم.
qid = "{qid}"
q = BY_ID[qid]
chosen = q["fields"][0]["answer"]
reason = q["fields"][1]["answer"]

print("prompt:", q["prompt"])
print("chosen :", chosen)
print("reason :", reason)

# The chosen text must be one of the schema options for this question.
schema = json.loads((ROOT / "assignment/source/Day4/Day4_Grading/question_schema.json").read_text(encoding="utf-8"))
raw = json.dumps(schema, ensure_ascii=False)
print("option present in schema:", chosen in raw)

import re
slides = ROOT / "docs" / "generated" / "slides_readable.txt"
cited = re.findall(r"اسلايد\\s*([0-9\\u06F0-\\u06F9]+)", reason)
print("cited slide(s):", cited)
if slides.is_file() and cited:
    text = slides.read_text(encoding="utf-8")
    marker = "# اسلايد " + cited[0]
    start = text.find(marker)
    print("--- slide excerpt ---")
    print(text[start:start + 600] if start >= 0 else "slide heading not found verbatim")
'''


def practical_code(section: int, number: int, qid: str) -> str:
    """Sections 5-12: print the exact result keys the answer was read from."""
    if section == 5:
        key = f'S5["{SECTION5_NAMES[number]}"]'
        return f'''# 5.{number}: evidence read straight from the recorded run output.
spec = {key}
show("{SECTION5_NAMES[number]}", spec)
print("keys:", list(spec))
'''

    if section == 10:
        if number == 1:
            body = 'show("inventory", S10["inventory"])'
        elif number == 2:
            body = 'show("detector", S10["detector"])'
        elif number == 12:
            body = (
                'detail = REPORTS["checks"]["detail"]\n'
                'show("family table", detail)\n'
                'print("families tested:", REPORTS["checks"]["families_tested"])\n'
                'print("controls passed:", REPORTS["checks"]["controls_passed"])\n'
                'print("failed:", REPORTS["checks"]["failed"])'
            )
        else:
            family = FAMILY[number]
            body = (
                f'family = "{family}"\n'
                'show(f"control: {family}", REPORTS["checks"]["detail"][family])'
            )
        return f'''# 10.{number}: one threat family, its asset and its boundary control.
import json
REPORTS = json.loads((OUT / "redteam_reports.json").read_text(encoding="utf-8"))
S10 = S["section10"]
{body}
''' 

    exprs = SECTION_MAP[section][number]
    var = f"S{section}"
    # `!r` keeps the label a valid literal even though the key contains quotes.
    lines = "\n".join(f'show({e!r}, {e})' for e in exprs)
    return f'''# {section}.{number}: evidence for every reported field.
{var} = S["section{section}"]
{lines}
'''


def analysis(q: dict) -> str:
    """The Persian analysis cell: submitted answers plus the recorded rationale."""
    parts = []
    for field in q["fields"][::-1]:
        if field["kind"] == "textarea":
            continue
        parts.append(f"- {field['label']}: **{field['answer']}**")
    listed = "\n".join(parts)
    return f'''<div dir="rtl">

**پاسخ‌های ثبت‌شده در فرم**

{listed}

{q["rationale"]}

</div>'''


def main() -> int:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in bank["questions"]}
    order = [q["id"] for q in bank["questions"]]

    cells = template["cells"]
    code_positions = [i for i, c in enumerate(cells)
                      if c["cell_type"] == "code" and "".join(c["source"]).strip() == CODE_PLACEHOLDER]
    heading_positions = [i for i, c in enumerate(cells)
                         if c["cell_type"] == "markdown"
                         and "".join(c["source"]).startswith("### زیرسؤال")]

    if len(code_positions) != len(order):
        print(f"refusing: {len(code_positions)} code cells vs {len(order)} questions")
        return 1

    # Guard: the k-th heading must name the k-th bank question.
    mismatched = []
    for index, position in enumerate(heading_positions):
        found = re.search(r"([0-9۰-۹]+)\.([0-9۰-۹]+)", "".join(cells[position]["source"]))
        if not found or index >= len(order):
            continue
        if f"{found.group(1)}.{found.group(2)}" != order[index]:
            mismatched.append((position, order[index]))
    if mismatched:
        print("refusing: heading/bank order mismatch at", mismatched[:5])
        return 1

    filled_codes = 0
    filled_analysis = 0

    for cell_index, question_id in zip(code_positions, order):
        section, number = question_id.split(".")
        section, number = int(section), int(number)
        source = (conceptual_code(question_id) if section <= 4
                  else practical_code(section, number, question_id))
        cells[cell_index]["source"] = source.splitlines(keepends=True)
        cells[cell_index]["outputs"] = []
        cells[cell_index]["execution_count"] = None
        filled_codes += 1

        # the analysis cell sits right after the code cell
        follow = cell_index + 1
        if follow < len(cells) and cells[follow]["cell_type"] == "markdown" \
                and ANALYSIS_PLACEHOLDER in "".join(cells[follow]["source"]):
            cells[follow]["source"] = analysis(by_id[question_id]).splitlines(keepends=True)
            filled_analysis += 1

    # Insert the setup cell right after the title so later cells can run alone.
    setup = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": PREAMBLE.splitlines(keepends=True),
    }
    note = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## نحوهٔ بازتولید\n",
            "\n",
            "این نوت‌بوک از `Day4_Starter/Student_Template.ipynb` ساخته شده است. برای اجرای کامل:\n",
            "\n",
            "```\n",
            ".venv\\Scripts\\python.exe work\\sec06_12_pipeline\\run_all.py\n",
            "```\n",
            "\n",
            "خروجی‌ها در `Day4_Run_Output/` نوشته می‌شوند و سلول‌های شواهد همین اعداد را نشان می‌دهند.\n",
        ],
    }
    cells[1:1] = [note, setup]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(template, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"code cells filled : {filled_codes}")
    print(f"analysis filled   : {filled_analysis}")
    print(f"bytes             : {OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
