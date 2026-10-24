"""Profile every dataset file in the student pack and write docs/_data_probe.txt.

For JSONL files it reports the record count, the union of keys, and one sample
record. For CSV files it reports the header, row count and a sample row. It also
re-computes SHA-256 against `manifest.json` so we know the local copy is intact.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assignment" / "source" / "Day4" / "Day4_Datasets"

lines: list[str] = []
add = lines.append


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def profile_jsonl(path: Path) -> None:
    records = []
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if raw:
                records.append(json.loads(raw))
    keys: list[str] = []
    for record in records:
        for key in record:
            if key not in keys:
                keys.append(key)
    add(f"### {path.name}  ({len(records)} records)")
    add(f"keys: {', '.join(keys)}")
    sample = json.dumps(records[0], ensure_ascii=False) if records else "{}"
    add(f"sample: {sample[:700]}")
    add("")


def profile_csv(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    header, body = rows[0], rows[1:]
    add(f"### {path.name}  ({len(body)} rows)")
    add(f"columns: {', '.join(header)}")
    if body:
        pairs = ", ".join(f"{k}={v}" for k, v in zip(header, body[0]))
        add(f"sample: {pairs[:700]}")
    add("")


for folder in sorted(DATA.iterdir()):
    if not folder.is_dir():
        continue
    add(f"## {folder.name}")
    add("")
    for path in sorted(folder.iterdir()):
        if path.suffix == ".jsonl":
            profile_jsonl(path)
        elif path.suffix == ".csv":
            profile_csv(path)

add("## MANIFEST VERIFICATION")
manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
ok = 0
for entry in manifest:
    path = DATA / entry["path"]
    if not path.exists():
        add(f"MISSING  {entry['path']}")
        continue
    actual = sha256(path)
    if actual == entry["sha256"]:
        ok += 1
    else:
        add(f"MISMATCH {entry['path']}\n  expected {entry['sha256']}\n  actual   {actual}")
add(f"matched {ok}/{len(manifest)} files")

out = ROOT / "docs" / "generated" / "qa" / "_data_probe.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes); manifest ok={ok}/{len(manifest)}")
