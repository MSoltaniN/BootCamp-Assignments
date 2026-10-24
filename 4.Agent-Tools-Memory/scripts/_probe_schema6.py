"""Final check: catch-all parameter stripped from the published schema."""

from __future__ import annotations

import asyncio
import json

from mcp.server.mcpserver import MCPServer

srv = MCPServer("probe6")
CATCH_ALL = "zz_extra"


@srv.tool(name="get_employee")
def get_employee(employee_id: str, zz_extra: dict | None = None) -> dict:
    if zz_extra:
        return {"error": {"code": "extra_argument", "unexpected": sorted(zz_extra)}}
    return {"employee_id": employee_id}


def render(result) -> str:
    try:
        return " | ".join(c.text for c in result.content if hasattr(c, "text"))[:200]
    except Exception:
        return repr(result)[:200]


async def main() -> None:
    # strip the catch-all from the published contract, then forbid extras
    for tool in srv._tool_manager._tools.values():
        schema = dict(tool.parameters)
        props = dict(schema.get("properties", {}))
        props.pop(CATCH_ALL, None)
        required = [r for r in schema.get("required", []) if r != CATCH_ALL]
        tool.parameters = {
            **schema,
            "properties": props,
            "required": required,
            "additionalProperties": False,
        }

    print("published:", json.dumps((await srv.list_tools())[0].input_schema))
    print("valid  ->", render(await srv.call_tool("get_employee", {"employee_id": "x"})))
    print("extra  ->", render(
        await srv.call_tool("get_employee", {"employee_id": "x", "tenant": "org-b"})
    ))


asyncio.run(main())
