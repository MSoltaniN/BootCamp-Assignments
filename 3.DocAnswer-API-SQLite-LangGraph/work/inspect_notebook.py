"""Pre-submission hygiene and a human-readable sample of the executed notebook."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "deliverables" / "day3_notebook.ipynb"

FORBIDDEN = [
    "C:\\Users\\pc",
    "C:/Users/pc",
    "TEST-ONLY-KEY-not-a-real-secret",
    "sk-",
]


def main() -> int:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    raw = NOTEBOOK.read_text(encoding="utf-8")

    print("=== hygiene scan of the notebook ===")
    for needle in FORBIDDEN:
        print(f"  {'FOUND' if needle in raw else 'clean'}  {needle!r}")

    # TEST-ONLY-SECRET is a permitted fixture marker, but it must never sit in a *stored output*.
    outputs = []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        for output in cell.get("outputs", []):
            text = output.get("text", "")
            outputs.append("".join(text) if isinstance(text, list) else text)
    blob = "\n".join(outputs)
    print(f"  {'FOUND' if 'TEST-ONLY-SECRET' in blob else 'clean'}  'TEST-ONLY-SECRET' in stored outputs")

    codes = [line for line in raw.splitlines() if '"C-"' in line and "Users" in line]
    print("  personal paths in stored output:", len(codes))

    print("\n=== first sub-question as a reader sees it ===")
    cells = notebook["cells"]
    for index, cell in enumerate(cells):
        source = "".join(cell["source"])
        if cell["cell_type"] == "markdown" and source.startswith("## زیرسؤال ۵٫۱"):
            print("[markdown title+question]")
            print(source.strip()[:300])
            print("\n[code]")
            print("".join(cells[index + 1]["source"]).strip())
            print("\n[output]")
            out = cells[index + 1].get("outputs", [])
            for output in out:
                text = output.get("text", "")
                print("".join(text) if isinstance(text, list) else text)
            print("[analysis markdown, first 240 chars]")
            print("".join(cells[index + 2]["source"]).strip()[:240])
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
