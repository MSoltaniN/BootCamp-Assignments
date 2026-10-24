"""Try to force pydantic extra='forbid' on the SDK argument model."""

from __future__ import annotations

import asyncio
import json

from mcp.server.mcpserver import MCPServer

srv = MCPServer("probe7")


@srv.tool(name="get_employee")
def get_employee(employee_id: str) -> dict:
    return {"employee_id": employee_id}


def render(result) -> str:
    try:
        return " | ".join(c.text for c in result.content if hasattr(c, "text"))[:200]
    except Exception:
        return repr(result)[:200]


async def main() -> None:
    tool = srv._tool_manager._tools["get_employee"]
    meta = tool.fn_metadata
    print("arg_model:", meta.arg_model)
    print("config    :", meta.arg_model.model_config)

    # rebuild the model with extra='forbid'
    model = meta.arg_model
    model.model_config["extra"] = "forbid"
    model.model_rebuild(force=True)

    print("new config:", model.model_config)

    print("valid  ->", render(await srv.call_tool("get_employee", {"employee_id": "x"})))
    try:
        out = await srv.call_tool("get_employee", {"employee_id": "x", "tenant": "b"})
        print("extra  ->", render(out))
    except Exception as error:  # noqa: BLE001
        print("extra  -> RAISED", type(error).__name__, str(error)[:200])


asyncio.run(main())
