"""Trusted principal and scope enforcement.

The assignment's central security rule: `tenant` and the manager role must come
from the application's trusted principal, never from model arguments. This module
is the single place that decision lives, so every tool in sections 6-10 shares
one implementation.

Usage
-----
    from common import principal

    p = principal.Principal(tenant="org-a", department="finance", role="hr_reviewer")
    principal.assert_can_read(p, employee)      # raises ScopeError
    principal.allowed_documents(p, data.documents())
"""

from __future__ import annotations

from dataclasses import dataclass, field


class ScopeError(PermissionError):
    """Raised when a request crosses a tenant or department boundary."""

    def __init__(self, message: str, *, code: str = "scope_denied") -> None:
        super().__init__(message)
        self.code = code
        self.retryable = False

    def to_dict(self) -> dict:
        """Machine-readable, bounded error shape (question 6.8).

        Deliberately holds only a code, a short reason and a retry flag: no
        private arguments, no résumé text, no tenant identifiers.
        """
        return {
            "code": self.code,
            "retryable": self.retryable,
            "reason": str(self),
        }


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, established by the application, not the model."""

    tenant: str
    department: str
    role: str = "hr_reviewer"
    employee_id: str | None = None
    allowed_departments: frozenset[str] = field(default_factory=frozenset)

    def can_read_department(self, department: str) -> bool:
        if department == self.department:
            return True
        return department in self.allowed_departments

    def as_dict(self) -> dict:
        return {
            "tenant": self.tenant,
            "department": self.department,
            "role": self.role,
            "employee_id": self.employee_id,
            "allowed_departments": sorted(self.allowed_departments),
        }


def assert_can_read(principal_obj: Principal, employee: dict) -> None:
    """Reject cross-tenant and cross-department reads *before* any data leaves."""
    if employee.get("tenant") != principal_obj.tenant:
        raise ScopeError("employee belongs to another tenant", code="tenant_denied")
    department = employee.get("department", "")
    if not principal_obj.can_read_department(department):
        raise ScopeError("employee belongs to another department",
                         code="department_denied")


def filter_employees(principal_obj: Principal, employees: list[dict]) -> list[dict]:
    """Return only the records this principal may read."""
    allowed: list[dict] = []
    for employee in employees:
        try:
            assert_can_read(principal_obj, employee)
        except ScopeError:
            continue
        allowed.append(employee)
    return allowed


def allowed_documents(principal_obj: Principal, documents: list[dict]) -> list[dict]:
    """Documents visible to the principal, filtered *before* scoring or retrieval."""
    return [
        doc
        for doc in documents
        if doc.get("tenant") == principal_obj.tenant
        and principal_obj.can_read_department(doc.get("department", ""))
    ]


def strip_private(person: dict) -> dict:
    """Remove fields that must never reach a model or a tool result."""
    return {key: value for key, value in person.items() if key != "email"}


__all__ = [
    "Principal", "ScopeError", "assert_can_read", "filter_employees",
    "allowed_documents", "strip_private",
]
