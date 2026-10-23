"""Cross-check the rendered dashboard against the pandas reference.

Chrome dumps the post-JavaScript DOM; this script pulls the KPI card text out of
it and compares each one with a string formatted here, from reference.json.
That means the numbers a reviewer sees in the PDF are proven to be the numbers
pandas computed, not just numbers the page claims are right.

Usage:
    python verify.py out/dom.html
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def money(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        s = f"{a / 1e6:.1f}M"
    elif a >= 1e3:
        s = f"{a / 1e3:.1f}K"
    else:
        s = f"{a:.0f}"
    s = s.replace(".0K", "K").replace(".0M", "M")
    return ("\u2212$" if v < 0 else "$") + s


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: verify.py <dom.html>")
        return 2
    dom_path = Path(sys.argv[1])
    if not dom_path.exists():
        print(f"dom dump missing: {dom_path}")
        return 2

    dom = dom_path.read_text(encoding="utf-8", errors="replace")
    ref = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
    ans = ref["answers"]

    expected = {
        "sales": money(ref["sales"]),
        "profit": money(ref["profit"]),
        "orders": f"{ref['orders']:,}",
        "margin": f"{ref['margin'] * 100:.1f}%",
        "topRegion": ans["1.5 top_region_by_sales"],
        "worstSub": ans["1.7 worst_subcategory"],
    }

    found = dict(re.findall(r'data-k="(\w+)"[\s\S]{0,400}?class="k-value[^"]*">([^<]+)<', dom))

    print(f"{'kpi':<11} {'expected':<12} {'rendered':<12} result")
    ok = True
    for k, want in expected.items():
        got = (found.get(k) or "<missing>").strip()
        same = got == want
        ok &= same
        print(f"{k:<11} {want:<12} {got:<12} {'ok' if same else 'MISMATCH'}")

    integrity = "✓ 5/5 figures match" in dom
    print(f"{'integrity':<11} {'in-page check':<12} {'present' if integrity else 'absent':<12} "
          f"{'ok' if integrity else 'MISMATCH'}")

    if not (ok and integrity):
        print("\nFAILED: rendered figures disagree with the pandas reference")
        return 1
    print("\nPASSED: all rendered figures match the pandas reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
