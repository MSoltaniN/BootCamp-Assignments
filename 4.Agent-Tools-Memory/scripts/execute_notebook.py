"""Execute the submission notebook so every cell carries real output.

The notebook writes no graded artifact: it only reads `Day4_Run_Output/`. The
kernel is a fresh process on purpose, so a passing run also proves the answers
do not depend on state left behind in the authoring session.
"""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "deliverables" / "notebook" / "Day4_Submission.ipynb"

# 144 code cells, each printing a bounded payload; 40 s per cell is generous
# and the whole run finishes in well under two minutes on this machine.
CELL_TIMEOUT = 40


def main() -> int:
    notebook = nbformat.read(NB, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=CELL_TIMEOUT,
        kernel_name="bootcamp-day4",
        resources={"metadata": {"path": str(ROOT)}},
        allow_errors=True,
    )

    try:
        client.execute()
    except Exception as error:  # noqa: BLE001 - report, do not hide
        print("execution aborted:", type(error).__name__, str(error)[:300])

    code_cells = [c for c in notebook.cells if c.cell_type == "code"]
    errors = []
    empty = []
    for index, cell in enumerate(code_cells):
        failed = any(o.get("output_type") == "error" for o in cell.get("outputs", []))
        if failed:
            name = next(o["ename"] for o in cell["outputs"] if o.get("output_type") == "error")
            errors.append(f"code[{index}] {name}")
        elif not cell.get("outputs"):
            head = "".join(cell["source"]).strip().splitlines()
            empty.append(f"code[{index}] {head[0][:60] if head else '(blank)'}")

    nbformat.write(notebook, NB)
    print(f"code cells      : {len(code_cells)}")
    print(f"cells with error: {len(errors)}")
    for line in errors[:25]:
        print("   ", line)
    print(f"cells with no output: {len(empty)}")
    for line in empty[:25]:
        print("   ", line)
    print(f"bytes           : {NB.stat().st_size}")
    return 0 if not errors and not empty else 1


if __name__ == "__main__":
    sys.exit(main())
