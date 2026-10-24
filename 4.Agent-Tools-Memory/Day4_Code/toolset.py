"""Tool schemas and dispatcher for the Day 4 agent.

Three read-only tools, each with a strict JSON schema:
  * get_employee(employee_id)
  * get_department_context(department)
  * get_evidence(employee_id)

Design rules this module enforces:
  * `additionalProperties: false` on every argument object, so a model cannot
    smuggle a `tenant` argument past validation
  * `tenant` never appears in any schema -- it comes from the trusted principal
  * department is a closed enum
  * the employee tool strips `email` before returning
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

from common import data, principal  # noqa: E402


DEPARTMENTS = ["finance", "marketing", "sales"]


class ToolValidationError(ValueError):
    """A tool call that fails schema, scope or policy checks."""

    def __init__(self, message: str, *, code: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable

    def to_dict(self) -> dict:
        """Bounded, machine-readable error. Never carries private arguments."""
        return {"code": self.code, "retryable": self.retryable, "reason": str(self)}


TOOL_SCHEMAS: dict[str, dict] = {
    "get_employee": {
        "name": "get_employee",
        "description": (
            "Return one employee's documented skills inventory. "
            "Email is always removed. Requires the caller's own scope."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "required": ["employee_id"],
            "additionalProperties": False,
        },
    },
    "get_department_context": {
        "name": "get_department_context",
        "description": (
            "Return the policy for one department: required skills, minimum "
            "evidence, retention days and approval role."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "enum": DEPARTMENTS},
            },
            "required": ["department"],
            "additionalProperties": False,
        },
    },
    "get_evidence": {
        "name": "get_evidence",
        "description": (
            "Return verified evidence references for one employee. "
            "Text is included only for verified records."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "required": ["employee_id"],
            "additionalProperties": False,
        },
    },
}

READ_ONLY_TOOLS = frozenset(TOOL_SCHEMAS)
FORBIDDEN_CAPABILITIES = [
    "write_memory",
    "send_email",
    "exec_shell",
    "eval_code",
    "external_http",
    "delete_record",
]


def required_field_count(tool: str) -> int:
    return len(TOOL_SCHEMAS[tool]["input_schema"]["required"])


def validate_arguments(tool: str, arguments: dict) -> dict:
    """Reject unknown tools, extra keys, wrong types and out-of-enum values."""
    schema = TOOL_SCHEMAS.get(tool)
    if schema is None:
        raise ToolValidationError(f"unknown tool {tool!r}", code="unknown_tool")

    spec = schema["input_schema"]
    if not isinstance(arguments, dict):
        raise ToolValidationError("arguments must be an object", code="bad_arguments")

    allowed = set(spec["properties"])
    extra = set(arguments) - allowed
    if extra:
        # This is where a model-supplied `tenant` gets stopped.
        raise ToolValidationError(
            f"unexpected argument(s): {sorted(extra)}", code="extra_argument"
        )

    missing = set(spec["required"]) - set(arguments)
    if missing:
        raise ToolValidationError(
            f"missing required argument(s): {sorted(missing)}", code="missing_argument"
        )

    for name, value in arguments.items():
        rule = spec["properties"][name]
        if rule.get("type") == "string" and not isinstance(value, str):
            raise ToolValidationError(
                f"{name} must be a string", code="wrong_type"
            )
        if "enum" in rule and value not in rule["enum"]:
            raise ToolValidationError(
                f"{name} must be one of {rule['enum']}", code="out_of_enum"
            )
        if rule.get("type") == "string" and value == "":
            raise ToolValidationError(f"{name} must not be empty", code="empty_value")
    return arguments


def call_tool(tool: str, arguments: dict, caller: principal.Principal) -> dict:
    """Validate then execute. Scope is checked before any data leaves."""
    validate_arguments(tool, arguments)

    if tool == "get_employee":
        person = data.people_by_id().get(arguments["employee_id"])
        if person is None:
            raise ToolValidationError("unknown employee", code="not_found")
        principal.assert_can_read(caller, person)
        safe = principal.strip_private(person)
        return {
            "employee_id": safe["employee_id"],
            "tenant": safe["tenant"],
            "department": safe["department"],
            "evidence_count": len(safe["evidence"]),
            "verified_count": sum(1 for e in safe["evidence"] if e["verified"]),
        }

    if tool == "get_department_context":
        department = arguments["department"]
        if not caller.can_read_department(department):
            raise ToolValidationError(
                "department outside caller scope", code="department_denied"
            )
        policy = data.policy_by_scope().get((caller.tenant, department))
        if policy is None:
            raise ToolValidationError("no policy for scope", code="not_found")
        return {
            "tenant": policy["tenant"],
            "department": policy["department"],
            "required_skills": list(policy["required_skills"]),
            "min_evidence": policy["min_evidence"],
            "retention_days": policy["retention_days"],
            "approval_role": policy["approval_role"],
        }

    if tool == "get_evidence":
        person = data.people_by_id().get(arguments["employee_id"])
        if person is None:
            raise ToolValidationError("unknown employee", code="not_found")
        principal.assert_can_read(caller, person)
        return {
            "employee_id": person["employee_id"],
            "evidence": [
                {
                    "evidence_id": item["evidence_id"],
                    "skill": item["skill"],
                    "verified": item["verified"],
                    "source": item["source"],
                }
                for item in person["evidence"]
            ],
        }

    raise ToolValidationError(f"unknown tool {tool!r}", code="unknown_tool")


def toolset_fingerprint(extra_tools: list[dict] | None = None) -> dict:
    """Stable SHA-256 over tool names and schemas, so drift is detectable."""
    import hashlib

    payload = [
        {"name": name, "schema": spec["input_schema"]}
        for name, spec in sorted(TOOL_SCHEMAS.items())
    ]
    if extra_tools:
        payload.extend(extra_tools)
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    return {
        "tool_count": len(payload),
        "sha256": digest,
        "hex_length": len(digest),
        "tools": [t["name"] for t in payload],
    }


__all__ = [
    "TOOL_SCHEMAS", "READ_ONLY_TOOLS", "FORBIDDEN_CAPABILITIES", "DEPARTMENTS",
    "ToolValidationError", "required_field_count", "validate_arguments",
    "call_tool", "toolset_fingerprint",
]
