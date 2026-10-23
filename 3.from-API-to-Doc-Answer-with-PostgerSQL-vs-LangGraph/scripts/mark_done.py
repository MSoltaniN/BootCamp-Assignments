"""Flip checklist boxes for one section from ☐ to ◐.

Usage: python scripts/mark_done.py 9
The checklist uses aligned pipes, so the box is replaced in place rather than the whole line.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CHECKLIST = Path(__file__).resolve().parents[1] / "docs" / "03_question_checklist.md"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/mark_done.py <section-number>")
        return 2
    section = sys.argv[1]

    text = CHECKLIST.read_text(encoding="utf-8")
    pattern = re.compile(rf"^(\|\s*{re.escape(section)}\.\d+\s*\|.*?\|\s*)(☐)(\s*\|)$", re.M)
    updated, count = pattern.subn(lambda m: m.group(1) + "◐" + m.group(3), text)
    CHECKLIST.write_text(updated, encoding="utf-8")
    print(f"section {section}: {count} rows marked ◐")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
