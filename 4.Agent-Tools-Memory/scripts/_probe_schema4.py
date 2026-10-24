"""Verify the strict-schema trick and how resources must be declared."""

from __future__ import annotations

import asyncio
import json

from mcp.server.mcpserver import MCPServer

srv = MCPServer("probe4")


@srv.tool(name="get_employee")
def get_employee(employee_id: str, **extra: object) -> dict:
    if extra:
        return {"error": {"code": "extra_argument", "unexpected": sorted(extra)}}
    return {"employee_id": employee_id}


@srv.resource("policy://finance", name="finance_policy")
def finance_policy() -> str:
    return '{"department": "finance"}'


@srv.resource("policy://{department}", name="policy_by_department")
def policy_by_department(department: str) -> str:
    return json.dumps({"department": department})


def render(result) -> str:
    try:
        return " | ".join(c.text for c in result.content if hasattr(c, "text"))[:200]
    except Exception:
        return repr(result)[:200]


async def main() -> None:
    # post-process schema: hide **extra, publish strict, forbid extras
    for tool in srv._tool_manager._tools.values():
        schema = {k: v for k, v in tool.parameters.items() if k != "extra"}
        schema["properties"] = {
            k: v for k, v in schema.get("properties", {}).items() if k != "extra"
        }
        if "extra" in schema.get("required", []):
            schema["required"] = [r for r in schema["required"] if r != "extra"]
        schema["additionalProperties"] = False
        tool.parameters = schema

    print("published:", json.dumps((await srv.list_tools())[0].input_schema))

    print("valid  ->", render(await srv.call_tool("get_employee", {"employee_id": "x"})))
    print("extra  ->", render(
        await srv.call_tool("get_employee", {"employee_id": "x", "tenant": "org-b"})
    ))

    res = await srv.list_resources()
    tmpl = await srv.list_resource_templates()
    print("resources:", [str(r.uri) for r in res] if isinstance(res, list) else res)
    print("templates:", [t.uriTemplate for t in tmpl] if isinstance(tmpl, list) else tmpl)


asyncio.run(main())
