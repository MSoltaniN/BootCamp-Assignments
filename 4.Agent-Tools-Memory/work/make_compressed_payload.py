"""Gzip + base64 the form payload so it can be shipped to the browser in chunks.

The page is HTTPS and blocks plain-HTTP localhost fetches, so the payload has to
travel through the evaluate channel. Persian analysis text compresses well, so
gzip keeps the number of chunks small. The browser side does

    base64 -> Uint8Array -> DecompressionStream('gzip') -> JSON.parse

and needs no network access at all.
"""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Day4_Run_Output" / "form_payload_all.json"

data = RAW.read_bytes()
packed = gzip.compress(data, compresslevel=9)
encoded = base64.b64encode(packed).decode("ascii")

out = ROOT / "Day4_Run_Output" / "form_payload_b64.txt"
out.write_text(encoded, encoding="utf-8")

print(f"raw      {len(data):>8} bytes")
print(f"gzip     {len(packed):>8} bytes")
print(f"base64   {len(encoded):>8} chars")
print(f"chunks@20k {len(encoded) // 20000 + 1}")
