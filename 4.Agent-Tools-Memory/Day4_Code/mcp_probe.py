"""Spawn the MCP server over stdio and exercise discovery plus a real call.

This is a genuine subprocess handshake: the client launches the server, performs
`initialize`, lists capabilities, invokes a tool and sends two out-of-scope
requests to prove the server rejects them.

Run:
    .venv\\Scripts\\python.exe Day4_Code/mcp_probe.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "Day4_Code" / "mcp_server.py"


async def probe() -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env=None,
    )

    result: dict = {"connected": False, "errors": []}

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result["connected"] = True

            tools = await session.list_tools()
            result["tools"] = sorted(t.name for t in tools.tools)

            # `policy://{department}` is a template, so it appears under
            # list_resource_templates rather than list_resources.
            resources = await session.list_resources()
            result["resources"] = [str(r.uri) for r in resources.resources]
            try:
                templates = await session.list_resource_templates()
                result["resource_templates"] = [
                    t.uriTemplate for t in templates.resourceTemplates
                ]
            except Exception:  # noqa: BLE001
                result["resource_templates"] = []

            prompts = await session.list_prompts()
            result["prompts"] = [p.name for p in prompts.prompts]

            # a real tools/call
            try:
                call = await session.call_tool(
                    "get_department_context", {"department": "finance"}
                )
                payload = call.content[0].text if call.content else ""
                result["call_ok"] = bool(payload)
                result["call_preview"] = payload[:200]
            except Exception as error:  # noqa: BLE001
                result["call_ok"] = False
                result["errors"].append(f"call: {error}")

            # out-of-scope department (outside the server principal's scope)
            try:
                denied = await session.call_tool(
                    "get_department_context", {"department": "marketing"}
                )
                text = denied.content[0].text if denied.content else ""
                result["marketing_rejected"] = not json.loads(text).get(
                    "department"
                )
                result["marketing_response"] = text[:160]
            except Exception as error:  # noqa: BLE001
                result["marketing_rejected"] = True
                result["marketing_response"] = str(error)[:160]

            # invalid department, outside the enum
            try:
                bad = await session.call_tool(
                    "get_department_context", {"department": "legal"}
                )
                text = bad.content[0].text if bad.content else ""
                result["invalid_department_rejected"] = "error" in text
                result["invalid_response"] = text[:160]
            except Exception as error:  # noqa: BLE001
                result["invalid_department_rejected"] = True
                result["invalid_response"] = str(error)[:160]

            # a tenant argument must be impossible
            try:
                extra = await session.call_tool(
                    "get_employee",
                    {"employee_id": "X-83c9e5db8f89697f", "tenant": "org-b"},
                )
                text = extra.content[0].text if extra.content else ""
                result["extra_argument_rejected"] = (
                    "Extra inputs are not permitted" in text or "extra_forbidden" in text
                )
                result["extra_argument_response"] = text[:160]
            except Exception as error:  # noqa: BLE001
                result["extra_argument_rejected"] = True
                result["extra_argument_response"] = str(error)[:160]

    return result


def main() -> int:
    try:
        outcome = asyncio.run(probe())
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"connected": False, "error": str(error)[:300]}, indent=2))
        return 1

    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("connected") else 1


if __name__ == "__main__":
    raise SystemExit(main())
