"""Report the shapes of the answer bank and the two result bundles."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "generated"
OUT = GEN / "shape_report.txt"

lines: list[str] = []
add = lines.append


def walk(node, prefix="", depth=0, limit=90):
    if depth > 2:
        return
    if isinstance(node, dict):
        keys = list(node.keys())
        add(f"{prefix}dict[{len(keys)}] -> {keys[:12]}")
        for key in keys[:8]:
            walk(node[key], prefix + f"  {key}.", depth + 1, limit)
    elif isinstance(node, list):
        add(f"{prefix}list[{len(node)}]")
        if node:
            walk(node[0], prefix + "  [0].", depth + 1, limit)
    else:
        text = repr(node)
        add(f"{prefix}{type(node).__name__} = {text[:limit]}")


bank = json.loads((GEN / "question_bank.json").read_text(encoding="utf-8"))
add("=== question_bank ===")
add(f"top keys: {list(bank.keys())[:10]}")
sections = bank.get("sections") or bank.get("questions") or bank
if isinstance(sections, dict):
    first = next(iter(sections))
    add(f"first section key: {first}")
    walk(sections[first], "  ")
elif isinstance(sections, list):
    walk(sections[0], "  ")
add("")

for name in ("section5.json", "sections_6_12.json"):
    path = ROOT / "Day4_Run_Output" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    add(f"=== {name} ===")
    add(f"top keys: {list(data.keys())}")
    for key in list(data.keys())[:14]:
        value = data[key]
        kind = type(value).__name__
        extra = f"[{len(value)}]" if isinstance(value, (list, dict)) else ""
        add(f"  {key}: {kind}{extra}")
    add("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT.name} lines={len(lines)}")
