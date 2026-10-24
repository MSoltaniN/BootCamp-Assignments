"""Split the base64 payload into fixed-size chunk files for the browser."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "Day4_Run_Output" / "form_payload_b64.txt"
text = src.read_text(encoding="utf-8")

SIZE = 20000
written = []
for index, start in enumerate(range(0, len(text), SIZE)):
    chunk = text[start : start + SIZE]
    path = ROOT / "Day4_Run_Output" / f"chunk_{index}.txt"
    path.write_text(chunk, encoding="utf-8")
    written.append((path.name, len(chunk)))

print(f"total {len(text)} chars in {len(written)} chunks")
for name, size in written:
    print(f"  {name}  {size}")
