"""Smoke-test the shared loaders and the question bank.

Run after installing dependencies:

    python work/smoke_test.py

Prints ASCII-only so it stays readable on a cp1256 console; the Persian details
live in the data files.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

from common import data, paths, principal  # noqa: E402


def main() -> int:
    failures: list[str] = []

    def check(label: str, actual: object, expected: object) -> None:
        ok = actual == expected
        status = "ok  " if ok else "FAIL"
        print(f"  [{status}] {label:<28} {actual!r}")
        if not ok:
            failures.append(f"{label}: expected {expected!r}, got {actual!r}")

    print("== file presence ==")
    for name in ("PEOPLE", "DOCUMENTS", "REQUESTS_FILE", "LABELS", "EVENTS",
                 "MODEL_RESPONSES", "REDTEAM", "RUNS", "SPANS", "TRAFFIC",
                 "MANIFEST", "QUESTION_SCHEMA", "CHECKER"):
        path = getattr(paths, name)
        check(name, path.exists(), True)

    print("\n== record counts ==")
    check("people", len(data.people()), 180)
    check("department_context", len(data.department_context()), 6)
    check("documents", len(data.documents()), 96)
    check("budget_parts", len(data.budget_parts()), 8)
    check("requests", len(data.requests()), 360)
    check("labels", len(data.labels()), 280)
    check("events", len(data.events()), 720)
    check("model_responses", len(data.model_responses()), 76)
    check("error_schedule", len(data.error_schedule()), 6)
    check("redteam", len(data.redteam()), 180)
    check("redteam attacks", len(data.redteam_attacks()), 120)
    check("redteam benign", len(data.redteam_benign()), 60)
    check("redteam attack families", len(data.redteam_families()), 10)
    check("attacks per family", sorted({len(v) for v in data.redteam_families().values()}), [12])
    check("runs", len(data.runs()), 640)
    check("spans", len(data.spans()), 2560)
    check("prices", len(data.prices()), 1)
    check("audit_groups", len(data.audit_groups()), 180)
    check("traffic", len(data.traffic()), 600)

    print("\n== split sizes ==")
    check("train requests", len(data.requests_by_split("train")), 200)
    check("dev requests", len(data.requests_by_split("dev")), 80)
    check("test requests", len(data.requests_by_split("test")), 80)
    check("train labelled", len(data.labelled_requests("train")), 200)
    check("dev labelled", len(data.labelled_requests("dev")), 80)

    print("\n== duplicate event_key in rollout (idempotency exercise) ==")
    keys = [row["event_key"] for row in data.traffic()]
    unique_keys = len(set(keys))
    check("event_key unique count", unique_keys < len(keys), True)
    print(f"         keys={len(keys)} unique={unique_keys}")

    print("\n== manifest integrity ==")
    check("manifest entries", len(data.manifest()), 16)
    check("all files listed", all((paths.DATA / item["path"]).exists()
                                 for item in data.manifest()), True)

    print("\n== question bank ==")
    bank = data.question_bank()
    check("assignment id", bank["assignment"], "DataMining_Bootcamp_Day4_Assignment")
    check("schema_version", bank["schema_version"], "2.1")
    check("revision", bank["revision"], "2026-10-16-r2")
    check("sections", bank["totals"]["sections"], 12)
    check("questions", bank["totals"]["questions"], 144)
    check("points", bank["totals"]["points"], 100.0)
    check("choice fields", bank["totals"]["choice_fields"], 120)
    check("number fields", bank["totals"]["number_fields"], 132)
    check("short fields", bank["totals"]["short_fields"], 64)
    check("textarea fields", bank["totals"]["textarea_fields"], 104)
    check("parser warnings", len(bank["warnings"]), 0)

    print("\n== principal / scope ==")
    inbox = principal.Principal(tenant="org-a", department="finance")
    same = {"tenant": "org-a", "department": "finance", "employee_id": "x"}
    other_tenant = {"tenant": "org-b", "department": "finance", "employee_id": "y"}
    other_dept = {"tenant": "org-a", "department": "legal", "employee_id": "z"}

    principal.assert_can_read(inbox, same)
    print("  [ok  ] same scope allowed")

    for label, employee in (("other tenant", other_tenant), ("other dept", other_dept)):
        try:
            principal.assert_can_read(inbox, employee)
        except principal.ScopeError as error:
            print(f"  [ok  ] {label} denied ({error.code})")
        else:
            failures.append(f"{label} was not denied")
            print(f"  [FAIL] {label} allowed")

    visible = principal.allowed_documents(inbox, data.documents())
    check("documents visible to org-a/finance", 0 < len(visible) < 96, True)
    print(f"         visible={len(visible)} of {len(data.documents())}")

    print()
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for failure in failures:
            print("  -", failure)
        return 1

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
