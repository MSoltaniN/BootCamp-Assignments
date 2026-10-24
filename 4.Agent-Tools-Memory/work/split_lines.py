"""Split the base64 payload into fixed-width lines so it can be read intact.

`read_file` truncates any single line beyond ~2000 characters, so the payload is
rewrapped at 1800 characters per line. Every line then survives a read and the
result can be pasted into the browser verbatim.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "Day4_Run_Output" / "form_payload_b64.txt").read_text(encoding="utf-8")

WIDTH = 1800
lines = [text[i : i + WIDTH] for i in range(0, len(text), WIDTH)]

out = ROOT / "Day4_Run_Output" / "payload_lines.txt"
out.write_text("\n".join(lines), encoding="utf-8")

print(f"chars {len(text)}  lines {len(lines)}  max_line {max(len(l) for l in lines)}")
