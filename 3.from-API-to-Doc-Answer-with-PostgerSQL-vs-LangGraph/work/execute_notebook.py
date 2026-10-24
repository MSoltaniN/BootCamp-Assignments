"""Execute the deliverable notebook in place so every code cell has stored output.

The grader reads the notebook and never runs it, so outputs must be present in the file. This uses
`nbclient` directly rather than inventing outputs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "deliverables" / "day3_notebook.ipynb"


def main() -> int:
    import nbformat
    from nbclient import NotebookClient

    notebook = nbformat.reads(NOTEBOOK.read_text(encoding="utf-8"), as_version=4)
    client = NotebookClient(
        notebook,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
        allow_errors=False,
    )
    client.execute()

    code_cells = [c for c in notebook.cells if c.cell_type == "code"]
    with_output = [c for c in code_cells if c.get("outputs")]
    print(f"code cells      : {len(code_cells)}")
    print(f"with output     : {len(with_output)}")
    print(f"without output  : {len(code_cells) - len(with_output)}")
    empty = [c for c in code_cells if not c.get("outputs")]
    for cell in empty[:5]:
        print("  empty cell:", "".join(cell.source).strip()[:60])

    nbformat.write(notebook, str(NOTEBOOK))
    total_chars = sum(len(o.get("text", "")) for c in code_cells for o in c.get("outputs", []))
    print(f"output characters stored: {total_chars:,}")
    return 0 if len(with_output) == len(code_cells) else 1


if __name__ == "__main__":
    sys.exit(main())
