"""Map the structure of Student_Template.ipynb to a UTF-8 report.

The template has 301 markdown and 144 code cells. The markdown cells carry the
question prompts; the code cells are the slots where each answer's code goes.
This probe records how a question block is laid out so the builder can place
answers deterministically instead of guessing.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "assignment" / "source" / "Day4" / "Day4_Starter" / "Student_Template.ipynb"
OUT = ROOT / "docs" / "generated" / "nb_structure.txt"


def main() -> None:
    nb = json.loads(NB.read_text(encoding="utf-8"))
    cells = nb["cells"]
    lines: list[str] = []
    add = lines.append

    add(f"cells={len(cells)}")
    add(f"nbformat={nb['nbformat']}.{nb['nbformat_minor']}")
    add(f"kernelspec={nb['metadata'].get('kernelspec')}")
    add("")

    # Which markdown cells announce a sub-question?
    qid_re = re.compile(r"(?:زیرسؤال|زیرسوال|^#*\s*)(\d{1,2})\.(\d{1,2})")
    markers: list[tuple[int, str]] = []
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "markdown":
            continue
        text = "".join(cell["source"])
        found = qid_re.search(text)
        if found:
            markers.append((index, f"{found.group(1)}.{found.group(2)}"))

    add(f"markdown cells carrying a sub-question number: {len(markers)}")
    add("")
    add("=== first 24 markers (cell_index, qid, how many cells until next marker) ===")
    for position, (index, qid) in enumerate(markers[:24]):
        following = markers[position + 1][0] if position + 1 < len(markers) else len(cells)
        add(f"  idx={index:3d} qid={qid:6s} span={following - index}")
    add("")

    add("=== raw dump of cells 0..40 ===")
    for index, cell in enumerate(cells[:41]):
        source = "".join(cell["source"])
        kind = cell["cell_type"]
        head = source.strip().splitlines()[0][:100] if source.strip() else "(empty)"
        add(f"--- cell {index} [{kind}] lines={len(source.splitlines())}")
        add(f"    head: {head}")
        if kind == "code":
            add(f"    body: {source.strip()[:300]}")
    add("")

    # Distinguish template placeholder code from real code.
    placeholder = sum(
        1
        for cell in cells
        if cell["cell_type"] == "code" and not "".join(cell["source"]).strip()
    )
    add(f"empty code cells: {placeholder} of 144")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.name} lines={len(lines)} cells={len(cells)}")


if __name__ == "__main__":
    main()
