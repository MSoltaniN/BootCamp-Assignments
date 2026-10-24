"""List the exact result keys so every question id can be bound to its output."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "generated" / "keys_report.txt"

lines: list[str] = []
add = lines.append

s5 = json.loads((ROOT / "Day4_Run_Output" / "section5.json").read_text(encoding="utf-8"))
add("=== section5 result keys ===")
for key, value in s5.items():
    if isinstance(value, dict):
        add(f"  {key}: {list(value.keys())}")
    else:
        add(f"  {key}: {type(value).__name__}")
add("")

data = json.loads((ROOT / "Day4_Run_Output" / "sections_6_12.json").read_text(encoding="utf-8"))
add("=== sections 6-12 child keys ===")
for key in sorted(k for k in data if k.startswith("section")):
    value = data[key]
    add(f"[{key}]")
    for child, sub in value.items():
        if isinstance(sub, dict):
            add(f"  {child}: {list(sub.keys())[:10]}")
        elif isinstance(sub, list):
            add(f"  {child}: list[{len(sub)}]")
        else:
            add(f"  {child}: {type(sub).__name__} = {str(sub)[:60]}")
    add("")

add("=== handoff_check ===")
add(json.dumps(data.get("handoff_check"), ensure_ascii=False)[:600])

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT.name} lines={len(lines)}")
