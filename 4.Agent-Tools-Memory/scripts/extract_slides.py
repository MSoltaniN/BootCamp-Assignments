"""Extract the Day 4 slide deck so question references can be resolved.

The PDF filename is Persian and does not survive a cp1256 console, so the deck is
found by glob and all output is written as UTF-8.

Two details matter for readability:

  * `extraction_mode="layout"` keeps the visual arrangement of each slide, which
    preserves the logical (right-to-left) order of the Persian text. The default
    mode interleaves words and produces unusable output.
  * The exporter embeds Arabic *presentation forms* (U+FE70..U+FEFF). NFKC
    normalisation maps them back to base letters so the text is searchable and
    renders correctly in any editor.

Outputs
-------
docs/generated/slides_text.txt     all pages, tabled by slide number
docs/generated/qa/_slides_probe.txt  page count and a short preview per page
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
QA = GEN / "qa"


def find_deck() -> Path:
    candidates = sorted(ROOT.glob("*.pdf"))
    if not candidates:
        raise SystemExit("no PDF found in the project root")
    for path in candidates:
        if "Agentic" in path.name or "بوت" in path.name:
            return path
    return candidates[0]


def clean(text: str) -> str:
    """Normalise presentation forms and drop fully blank lines."""
    text = unicodedata.normalize("NFKC", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line.strip())


def main() -> int:
    deck = find_deck()
    QA.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(deck))
    pages: list[str] = []
    probe: list[str] = [
        f"file  : {deck.name}",
        f"pages : {len(reader.pages)}",
        "",
    ]

    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text(extraction_mode="layout") or ""
        except Exception:  # noqa: BLE001 - layout mode is not universal
            try:
                raw = page.extract_text() or ""
            except Exception as error:  # noqa: BLE001
                raw = f"[extract failed: {error}]"

        body = clean(raw)
        pages.append(f"\n{'=' * 70}\nSLIDE {index}\n{'=' * 70}\n{body}\n")

        preview = body.splitlines()[:3]
        probe.append(f"--- slide {index} (chars={len(body)})")
        for line in preview:
            probe.append(f"    {line.strip()[:120]}")

    (GEN / "slides_text.txt").write_text("".join(pages), encoding="utf-8")
    (QA / "_slides_probe.txt").write_text("\n".join(probe), encoding="utf-8")

    empty = [i for i, page in enumerate(pages, start=1) if len(page) < 110]
    print(f"pages : {len(reader.pages)}")
    print(f"chars : {sum(len(p) for p in pages)}")
    print(f"empty : {empty if empty else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
