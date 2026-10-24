"""Print selected slides with Persian glyph order restored.

`pypdf` returns Persian as *visual* order (right-to-left already applied), so each
run of Persian characters reads backwards. Reversing the whole line fixes Persian
but breaks embedded Latin words, so this script reverses only the Persian runs and
leaves ASCII words in place.

Usage
-----
    python scripts/show_slides.py 3 4 5 11 12
    python scripts/show_slides.py            # prints every slide
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = ROOT / "docs" / "generated" / "slides_text.txt"
OUT = ROOT / "docs" / "generated" / "slides_fa.txt"

# Persian/Arabic block plus the presentation forms used by the PDF exporter.
PERSIAN = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]+")
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_.\-/]*")


def fix_line(line: str) -> str:
    """Restore readable Persian from a PDF that emitted visual-order glyphs.

    Two distortions have to be undone:

      1. The exporter writes Arabic *presentation forms* (U+FE70..U+FEFF) instead
         of base letters, so NFKC normalisation is applied first to recover the
         plain characters.
      2. Each run is already laid out right-to-left, i.e. stored backwards, so
         the Persian runs are reversed while Latin runs keep their order.
    """
    line = unicodedata.normalize("NFKC", line)

    tokens = re.findall(
        r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]+|[A-Za-z][A-Za-z0-9_.\-/]*|[\d\s\W]+",
        line,
    )
    out: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            # a run of Persian + neutral characters: reverse it
            out.append("".join(buffer)[::-1])
            buffer.clear()

    for token in tokens:
        if PERSIAN.fullmatch(token):
            buffer.append(token)
        elif LATIN.fullmatch(token):
            flush()
            out.append(token)
        else:
            # neutral (digits, spaces, punctuation) stays with the Persian run
            buffer.append(token)
    flush()

    result = "".join(out)
    return re.sub(r"[ \t]{2,}", " ", result).strip()


def load_slides() -> dict[int, list[str]]:
    raw = TEXT.read_text(encoding="utf-8")
    parts = re.split(r"={70}\nSLIDE (\d+)\n={70}\n", raw)
    slides: dict[int, list[str]] = {}
    for index in range(1, len(parts), 2):
        number = int(parts[index])
        slides[number] = parts[index + 1].strip().splitlines()
    return slides


def main() -> int:
    slides = load_slides()
    wanted = [int(arg) for arg in sys.argv[1:] if arg.isdigit()] or sorted(slides)

    # The Windows console is cp1256 and cannot render Persian, so nothing is
    # printed; the normalised text goes to OUT and is read from there.
    output: list[str] = []
    written = 0
    for number in wanted:
        if number not in slides:
            continue
        written += 1
        output.append(f"\n{'=' * 70}\nSLIDE {number}\n{'=' * 70}")
        for line in slides[number]:
            fixed = fix_line(line)
            if fixed:
                output.append(fixed)
        output.append("")

    OUT.write_text("\n".join(output), encoding="utf-8")
    print(f"slides written: {written} -> {OUT.name} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
