"""Summarise the structure of `Student_Template.ipynb` into docs/_nb_probe.txt."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "assignment" / "source" / "Day4" / "Day4_Starter" / "Student_Template.ipynb"

nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

lines: list[str] = []
add = lines.append
add(f"total cells: {len(cells)}")
add("")

counts: dict[str, int] = {}
for cell in cells:
    counts[cell["cell_type"]] = counts.get(cell["cell_type"], 0) + 1
add(f"by type: {counts}")
add("")

add("== CELL INDEX ==")
for index, cell in enumerate(cells):
    source = "".join(cell["source"])
    first = source.strip().splitlines()[0][:120] if source.strip() else "(empty)"
    tag = ""
    if cell["cell_type"] == "code":
        tag = f" exec={cell.get('execution_count')} outputs={len(cell.get('outputs', []))}"
    add(f"[{index:>3}] {cell['cell_type']:<8}{tag}  {first}")
add("")

add("== MARKDOWN HEADINGS ==")
for index, cell in enumerate(cells):
    if cell["cell_type"] != "markdown":
        continue
    for line in "".join(cell["source"]).splitlines():
        if line.lstrip().startswith("#"):
            add(f"[{index:>3}] {line.strip()[:160]}")
add("")

add("== CODE STUBS (first 25 code cells, first 20 lines each) ==")
shown = 0
for index, cell in enumerate(cells):
    if cell["cell_type"] != "code":
        continue
    shown += 1
    if shown > 25:
        break
    source = "".join(cell["source"]).splitlines()
    add(f"--- cell {index} ({len(source)} lines)")
    for line in source[:20]:
        add(f"    {line}")
    add("")

out = ROOT / "docs" / "generated" / "qa" / "_nb_probe.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes); cells={len(cells)}")
