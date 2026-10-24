"""Real MCP server over stdio: three read tools, one resource, one prompt.

Three protocol details drive this file:

  * `stdout` belongs to the JSON-RPC stream, so all diagnostics go to `stderr`.
  * A tool that raises makes the SDK emit a generic "Error executing tool"
    message. Section 6.8 wants a *bounded, structured* error, so each tool catches
    validation failures and returns a small JSON object instead.
  * The SDK derives each tool's argument model from the Python signature and, by
    default, silently *drops* unknown keys -- a model-supplied `tenant` would be
    accepted and ignored. `harden_schemas()` rebuilds those models with
    `extra="forbid"` and publishes `additionalProperties: false`, so an extra key
    is rejected at the protocol boundary.

Run standalone to inspect it:
    .venv\\Scripts\\python.exe Day4_Code/mcp_server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "Day4_Code"))

from common import principal  # noqa: E402
from toolset import (  # noqa: E402
    DEPARTMENTS,
    TOOL_SCHEMAS,
    ToolValidationError,
    call_tool,
)

# mcp 2.x renamed FastMCP to MCPServer. Support both so the file runs under either.
try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp >= 2
except ImportError:  # pragma: no cover - mcp 1.x
    from mcp.server.fastmcp import FastMCP  # type: ignore

SERVER_NAME = "day4-hr-tools"
SERVER_VERSION = "1.0.0"

# The server's own principal. In production this is the authenticated caller;
# here it is a fixture and the report says so.
SERVER_PRINCIPAL = principal.Principal(tenant="org-a", department="finance")

FORBIDDEN_CAPABILITIES = [
    "write_memory",
    "send_email",
    "exec_shell",
    "eval_code",
    "external_http",
    "delete_record",
]

mcp = FastMCP(SERVER_NAME, version=SERVER_VERSION)


def _log(message: str) -> None:
    """Diagnostics go to stderr; stdout is reserved for JSON-RPC."""
    print(message, file=sys.stderr)


def _safe(tool: str, arguments: dict) -> dict:
    """Run a tool, converting refusal into a bounded error object."""
    try:
        return call_tool(tool, arguments, SERVER_PRINCIPAL)
    except ToolValidationError as error:
        return {"error": error.to_dict()}
    except principal.ScopeError as error:
        return {"error": error.to_dict()}


@mcp.tool(name="get_employee")
def get_employee(employee_id: str) -> dict:
    """Return one employee's documented skills inventory (email removed)."""
    return _safe("get_employee", {"employee_id": employee_id})


@mcp.tool(name="get_department_context")
def get_department_context(department: str) -> dict:
    """Return the department policy: required skills, min evidence, retention."""
    return _safe("get_department_context", {"department": department})


@mcp.tool(name="get_evidence")
def get_evidence(employee_id: str) -> dict:
    """Return verified evidence references for one employee."""
    return _safe("get_evidence", {"employee_id": employee_id})


@mcp.resource("policy://finance", name="finance_policy",
              description="Finance department policy (read-only).")
def finance_policy() -> str:
    """Concrete resource so `list_resources` has an entry."""
    return json.dumps(
        _safe("get_department_context", {"department": "finance"}),
        ensure_ascii=False,
        indent=2,
    )


@mcp.prompt(name="skills_review")
def skills_review(employee_id: str) -> str:
    """Prompt template for a documented-skills review."""
    return (
        "Review the documented skills of employee {eid}.\n"
        "Rules:\n"
        "- Use only verified evidence.\n"
        "- Do not produce hiring, pay or promotion decisions.\n"
        "- Set decision to skills_inventory_only.\n"
        "- If a required skill has no verified evidence, list it as a limitation."
    ).format(eid=employee_id)


def harden_schemas(server) -> dict:
    """Make argument validation strict and publish `additionalProperties: false`.

    The SDK builds a pydantic model per tool from the function signature. Adding
    `extra="forbid"` to that model turns silently-dropped keys into a validation
    error. The published JSON Schema is then narrowed to match, so a client can
    see the strict contract before calling.
    """
    manager = getattr(server, "_tool_manager", None)
    tools = getattr(manager, "_tools", {}) if manager else {}

    hardened: list[str] = []
    for name, tool in tools.items():
        meta = getattr(tool, "fn_metadata", None)
        model = getattr(meta, "arg_model", None)
        if model is not None:
            model.model_config["extra"] = "forbid"
            model.model_rebuild(force=True)

        schema = dict(getattr(tool, "parameters", {}) or {})
        schema["additionalProperties"] = False
        tool.parameters = schema
        hardened.append(name)

    return {
        "hardened": hardened,
        "count": len(hardened),
        "additional_properties": False,
        "strict_extra": True,
    }


HARDENING = harden_schemas(mcp)


def capability_manifest() -> dict:
    """Machine-readable server contract, including the transport choice."""
    return {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "transport": "stdio",
        "sdk": "mcp (official)",
        "tools": sorted(TOOL_SCHEMAS),
        "resources": ["policy://finance"],
        "prompts": ["skills_review"],
        "departments": DEPARTMENTS,
        "forbidden_capabilities": FORBIDDEN_CAPABILITIES,
        "principal": SERVER_PRINCIPAL.as_dict(),
        "schema_hardening": HARDENING,
        "notes": [
            "stdout is reserved for JSON-RPC; logs go to stderr",
            "no tool accepts a tenant argument",
            "extra arguments are rejected, not dropped",
            "a2a is not implemented here",
        ],
    }


if __name__ == "__main__":
    _log(json.dumps(capability_manifest(), ensure_ascii=False))
    mcp.run(transport="stdio")
