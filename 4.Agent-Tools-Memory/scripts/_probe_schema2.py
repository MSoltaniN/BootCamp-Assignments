"""Test whether the published tool schema can be made strict after registration."""

from __future__ import annotations

import asyncio
import json

from mcp.server.mcpserver import MCPServer

srv = MCPServer("probe2")


@srv.tool(name="get_employee")
def get_employee(employee_id: str) -> dict:
    return {"employee_id": employee_id}


async def main() -> None:
    # show what the SDK generated
    before = (await srv.list_tools())[0]
    print("BEFORE:", json.dumps(before.input_schema, ensure_ascii=False))

    # post-process: add additionalProperties: false
    for tool in srv._tool_manager._tools.values():
        schema = dict(tool.parameters)
        schema["additionalProperties"] = False
        tool.parameters = schema

    after = (await srv.list_tools())[0]
    print("AFTER :", json.dumps(after.input_schema, ensure_ascii=False))

    # does strictness now reject an extra key?
    try:
        out = await srv.call_tool("get_employee", {"employee_id": "x", "tenant": "org-b"})
        print("EXTRA -> accepted:", json.dumps(out, ensure_ascii=False)[:160])
    except Exception as error:  # noqa: BLE001
        print("EXTRA -> rejected:", type(error).__name__, str(error)[:200])

    # resources: does a templated resource register?
    res = await srv.list_resources()
    tmpl = await srv.list_resource_templates()
    print("RESOURCES :", [str(r.uri) for r in res.resources])
    print("TEMPLATES :", [t.uriTemplate for t in tmpl.resourceTemplates])


asyncio.run(main())
