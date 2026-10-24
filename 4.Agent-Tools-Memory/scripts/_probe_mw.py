"""Dump the MCP server middleware API surface."""

from __future__ import annotations

import inspect

from mcp.server.mcpserver import middleware as mw

lines: list[str] = []
lines.append("module members:")
lines.append("  " + ", ".join(n for n in dir(mw) if not n.startswith("_")))

for name in dir(mw):
    if name.startswith("_"):
        continue
    obj = getattr(mw, name)
    if inspect.isclass(obj):
        lines.append("")
        lines.append(f"class {name}:")
        try:
            lines.append("  __init__" + str(inspect.signature(obj.__init__)))
        except Exception:
            pass
        methods = [m for m in dir(obj) if not m.startswith("_")]
        lines.append("  methods: " + ", ".join(methods))
        for method in methods:
            try:
                lines.append(f"    {method}{inspect.signature(getattr(obj, method))}")
            except Exception:
                pass

open("scripts/_mw_dump.txt", "w", encoding="utf-8").write("\n".join(lines))
print("written")
