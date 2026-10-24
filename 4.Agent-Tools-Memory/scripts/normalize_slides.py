"""Restore readable Persian in the extracted slide text.

The deck was exported with a PDF writer that stored each line in *visual* order:
every word's letters are reversed and the words themselves run right-to-left.
Rendering hides this, but plain-text extraction exposes it.

Undoing it needs three steps, applied per line:

  1. NFKC normalise, because the exporter used Arabic presentation forms
     (U+FE70..U+FEFF) instead of base letters.
  2. Reverse the whole line. This fixes both the letter order inside each word
     and the sequence of words.
  3. Re-reverse every run of Latin/numeric characters, which step 2 turned
     backwards (``Human-in-the-loop`` became ``pool-eht-ni-namuH``).

Reads  docs/generated/slides_text.txt
Writes docs/generated/slides_readable.txt
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "generated" / "slides_text.txt"
OUT = ROOT / "docs" / "generated" / "slides_readable.txt"

# Latin, digits and the joiners that legitimately appear inside a token.
LATIN_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.+\-/()]*[A-Za-z0-9]|[A-Za-z0-9]")
# Windows checkouts give CRLF, so both separators must be tolerated.
SLIDE_MARK = re.compile(r"={70}\r?\nSLIDE (\d+)\r?\n={70}\r?\n")


def unmirror(line: str) -> str:
    if not line.strip():
        return ""
    line = unicodedata.normalize("NFKC", line)
    flipped = line[::-1]
    # Step 3: the Latin tokens are now backwards; restore them in place.
    return LATIN_RUN.sub(lambda m: m.group(0)[::-1], flipped)


def main() -> int:
    raw = SRC.read_text(encoding="utf-8")
    parts = SLIDE_MARK.split(raw)

    out: list[str] = []
    slides = 0
    for index in range(1, len(parts), 2):
        number = parts[index]
        body = parts[index + 1]
        slides += 1
        out.append(f"\n{'=' * 70}\nSLIDE {number}\n{'=' * 70}")
        for line in body.splitlines():
            fixed = unmirror(line)
            if fixed.strip():
                # collapse the wide column padding the layout mode preserves
                out.append(re.sub(r"[ \t]{3,}", "  ", fixed.rstrip()))
        out.append("")

    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"slides: {slides} -> {OUT.name} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
