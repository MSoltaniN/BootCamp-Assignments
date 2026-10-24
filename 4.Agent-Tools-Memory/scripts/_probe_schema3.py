"""Determine whether additionalProperties:false on the published schema is enforced."""

from __future__ import annotations

import asyncio
import json

from mcp.server.mcpserver import MCPServer

srv = MCPServer("probe3")


@srv.tool(name="get_employee")
def get_employee(employee_id: str) -> dict:
    return {"employee_id": employee_id}


def render(result) -> str:
    """CallToolResult -> short text."""
    try:
        parts = [c.text for c in result.content if hasattr(c, "text")]
        return " | ".join(parts)[:220] or repr(result)[:220]
    except Exception:
        return repr(result)[:220]


async def main() -> None:
    for tool in srv._tool_manager._tools.values():
        schema = dict(tool.parameters)
        schema["additionalProperties"] = False
        tool.parameters = schema

    print("published:", json.dumps((await srv.list_tools())[0].input_schema))

    ok = await srv.call_tool("get_employee", {"employee_id": "x"})
    print("valid    ->", render(ok))

    try:
        bad = await srv.call_tool("get_employee", {"employee_id": "x", "tenant": "org-b"})
        print("extra    ->", render(bad))
    except Exception as error:  # noqa: BLE001
        print("extra    -> RAISED", type(error).__name__, str(error)[:200])

    res = await srv.list_resources()
    tmpl = await srv.list_resource_templates()
    print("resources:", res if not isinstance(res, list) else [str(r.uri) for r in res])
    print("templates:", [t.uriTemplate for t in tmpl] if isinstance(tmpl, list) else tmpl)


asyncio.run(main())
