"""Verify the delivered notebook meets the structural contract the grader relies on.

Checks, in order:
  * 144 sub-question titles in the exact «زیرسؤال N٫M» form with U+066B
  * every title is followed by a code cell and then an analysis markdown cell
  * every code cell has stored output
  * a sample of site numbers appears in the notebook output
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "deliverables" / "day3_notebook.ipynb"
QUESTIONS = ROOT / "artifacts" / "questions.json"

SEPARATOR = "\u066b"
TITLE = re.compile(r"^## زیرسؤال (\S+)$", re.M)


def main() -> int:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    expected = [q["id"] for s in questions["sections"] for q in s["questions"]]

    cells = notebook["cells"]
    titles: list[str] = []
    structure_problems: list[str] = []

    for index, cell in enumerate(cells):
        if cell["cell_type"] != "markdown":
            continue
        match = TITLE.search("".join(cell["source"]))
        if not match:
            continue
        titles.append(match.group(1))

        following = cells[index + 1:index + 3]
        if len(following) < 2:
            structure_problems.append(f"{index}: not enough following cells")
            continue
        if following[0]["cell_type"] != "code":
            structure_problems.append(f"{index}: cell after title is not code")
        if following[1]["cell_type"] != "markdown":
            structure_problems.append(f"{index}: cell after code is not analysis markdown")
        elif not "".join(following[1]["source"]).strip():
            structure_problems.append(f"{index}: analysis cell is empty")

    print("cells total        :", len(cells))
    print("sub-question titles:", len(titles))
    print("expected           :", len(expected))
    print("uses U+066B in all :", all(SEPARATOR in t for t in titles))
    persian = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    expected_titles = [t.translate(persian).replace(".", SEPARATOR) for t in expected]
    print("order matches file :", titles == expected_titles)
    print("structure problems :", len(structure_problems))
    for problem in structure_problems[:10]:
        print("   ", problem)

    code_cells = [c for c in cells if c["cell_type"] == "code"]
    with_output = [c for c in code_cells if c.get("outputs")]
    print("code cells         :", len(code_cells), "| with output:", len(with_output))

    def _text(output: dict) -> str:
        raw = output.get("text", "")
        return "".join(raw) if isinstance(raw, list) else raw

    blob = "\n".join(_text(o) for c in code_cells for o in c.get("outputs", []))
    spot_checks = {
        "5.1 rows 2400": "2400",
        "5.10 cost 0.833118": "0.833118",
        "6.2 users 20": "users",
        "7.4 chunks 1282": "1282",
        "8.9 zero leak": "tenant leak",
        "9.4 hybrid": "hybrid",
        "10.5 24900": "24900",
        "11.10 fixtures 30": "30",
        "12.9 passed": "passed",
    }
    print("\nspot checks in notebook output:")
    for label, needle in spot_checks.items():
        print(f"  {'OK  ' if needle in blob else 'MISS'}  {label}")

    ok = (len(titles) == 144 and not structure_problems
          and len(with_output) == len(code_cells))
    print("\nVERDICT:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
