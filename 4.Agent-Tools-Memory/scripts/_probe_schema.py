"""Check whether the MCP SDK rejects extra arguments when a tool declares **extra."""

from __future__ import annotations

import asyncio
import json
import sys

from mcp.server.mcpserver import MCPServer


srv = MCPServer("probe")


@srv.tool(name="echo_strict")
def echo_strict(employee_id: str, **extra: object) -> dict:
    if extra:
        return {"error": {"code": "extra_argument", "unexpected": sorted(extra)}}
    return {"employee_id": employee_id}


async def main() -> None:
    tools = await srv.list_tools()
    print("PUBLISHED SCHEMA:", json.dumps(tools[0].input_schema, indent=1))

    # valid call
    ok = await srv.call_tool("echo_strict", {"employee_id": "x"})
    print("VALID   ->", json.dumps(ok, ensure_ascii=False)[:160])

    # call with an extra key
    try:
        bad = await srv.call_tool("echo_strict", {"employee_id": "x", "tenant": "org-b"})
        print("EXTRA   ->", json.dumps(bad, ensure_ascii=False)[:200])
    except Exception as error:  # noqa: BLE001
        print("EXTRA   -> raised:", type(error).__name__, str(error)[:160])


asyncio.run(main())
