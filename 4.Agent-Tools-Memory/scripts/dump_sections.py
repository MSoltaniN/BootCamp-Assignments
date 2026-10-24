"""Dump one or more sections of the question bank as readable text.

Usage
-----
    python scripts/dump_sections.py 1 2 3 4
    python scripts/dump_sections.py 1        # only section 1

Writes docs/generated/sections_<list>.txt so the Windows console encoding is
never an issue.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
BANK = GEN / "question_bank.json"


def main() -> int:
    wanted = [arg for arg in sys.argv[1:] if arg.isdigit()] or ["1"]
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    sections = {s["number"]: s for s in bank["sections"]}

    lines: list[str] = []
    for number in wanted:
        section = sections.get(number)
        if section is None:
            continue
        group = [q for q in bank["questions"] if q["section"] == number]
        lines.append("=" * 72)
        lines.append(f"SECTION {number} - {section['title']}  ({section['points']:g} pts)")
        lines.append(f"dataset: {section['dataset']}")
        lines.append(f"intro  : {section['intro']}")
        lines.append("=" * 72)
        for question in group:
            lines.append("")
            lines.append(f"--- {question['id']}  ({question['points']:g} pts)  type={question['type']}")
            lines.append(f"Q: {question['prompt']}")
            for field in question["fields"]:
                if field["kind"] == "choice":
                    lines.append(f"  [{field['label']}] options:")
                    for index, option in enumerate(field["options"]):
                        lines.append(f"      ({chr(65 + index)}) {option}")
                elif field["kind"] == "number":
                    lines.append(f"  [{field['label']}] <number>")
                else:
                    lines.append(f"  [{field['label']}] <{field['kind']}>")
        lines.append("")

    out = GEN / f"sections_{'_'.join(wanted)}.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    total = sum(len([q for q in bank["questions"] if q["section"] == n]) for n in wanted)
    print(f"sections {wanted}: {total} questions -> {out.name} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
