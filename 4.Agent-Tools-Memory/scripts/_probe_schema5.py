"""Test the sentinel-parameter trick for rejecting extra arguments."""

from __future__ import annotations

import asyncio
import json

from mcp.server.mcpserver import MCPServer

srv = MCPServer("probe5")

SENTINEL = "__extra__"


@srv.tool(name="get_employee")
def get_employee(employee_id: str, __extra__: dict | None = None) -> dict:
    if __extra__:
        return {"error": {"code": "extra_argument", "unexpected": sorted(__extra__)}}
    return {"employee_id": employee_id}


def render(result) -> str:
    try:
        return " | ".join(c.text for c in result.content if hasattr(c, "text"))[:200]
    except Exception:
        return repr(result)[:200]


async def main() -> None:
    print("published:", json.dumps((await srv.list_tools())[0].input_schema))
    print("valid  ->", render(await srv.call_tool("get_employee", {"employee_id": "x"})))
    print("extra  ->", render(
        await srv.call_tool("get_employee", {"employee_id": "x", "tenant": "org-b"})
    ))


asyncio.run(main())
