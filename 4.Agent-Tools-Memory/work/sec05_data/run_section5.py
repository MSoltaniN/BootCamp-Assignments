"""Execute all twelve section-5 questions and persist the evidence.

Every number reported in the answer form comes from this run; nothing is typed by
hand. Outputs:

    Day4_Run_Output/section5.json                    machine-readable results
    Day4_Run_Output/section5_console.log             the run log
    Day4_Run_Output/coverage_by_department.png       chart for 5.12
    docs/generated/section5_report.md                Persian report (RTL)

Run with the venv interpreter:
    .venv\\Scripts\\python.exe work/sec05_data/run_section5.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work"))

from common import data, paths  # noqa: E402
from sec05_data import context_ops as ops  # noqa: E402


def main() -> int:
    paths.ensure_output_dirs()
    out_dir = paths.OUTPUT
    log: list[str] = []

    def log_line(message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        print(line)
        log.append(line)

    log_line("section 5 start")

    # 5.1 -----------------------------------------------------------------
    inventory = ops.dataset_inventory()
    log_line(
        f"5.1 people={inventory['people']} policies={inventory['policies']} "
        f"documents={inventory['documents']} splits={inventory['splits']}"
    )

    # 5.2 -----------------------------------------------------------------
    scope = ops.scope_filter()
    log_line(
        f"5.2 allowed={scope['allowed']}/{scope['total']} "
        f"other_tenant={scope['excluded_by_other_tenant']} "
        f"other_dept={scope['excluded_by_other_department']}"
    )

    # 5.3 -----------------------------------------------------------------
    budget = ops.allocate_budget(1200, 200)
    log_line(
        f"5.3 selected={budget['selected']} used={budget['used']} "
        f"remaining={budget['remaining']} capacity={budget['capacity']}"
    )

    # 5.4 -----------------------------------------------------------------
    tight = ops.budget_insufficient_control(600, 200)
    log_line(
        f"5.4 rejected={tight['rejected']} capacity={tight['capacity']} "
        f"mandatory={tight['mandatory_tokens']}"
    )

    # 5.5 -----------------------------------------------------------------
    retrieval = ops.retrieve_documents()
    log_line(
        f"5.5 retrieved={retrieval['retrieved']} from {retrieval['corpus_size']} "
        f"limit0_rejected={retrieval['limit_zero_rejected']}"
    )
    for item in retrieval["top"]:
        log_line(f"     {item['doc_id']}  score={item['score']}")

    # 5.6 -----------------------------------------------------------------
    sample_text = (
        "Employee contact record for review. "
        "Send the summary to ali.reza@example.invalid before Friday. "
        "The reconciliation total must match the ledger for Q3."
    )
    redaction = ops.redact_emails(sample_text)
    log_line(
        f"5.6 emails={redaction['emails_found']} "
        f"removed={redaction['email_removed']} "
        f"work_preserved={redaction['working_text_preserved']}"
    )

    # 5.7 -----------------------------------------------------------------
    dedupe = ops.deduplicate_documents()
    log_line(
        f"5.7 before={dedupe['before']} after={dedupe['after']} "
        f"removed={dedupe['removed']} chars {dedupe['before_chars']}->{dedupe['after_chars']}"
    )

    # 5.8 -----------------------------------------------------------------
    chosen = data.people()[0]["employee_id"]
    compression = ops.compress_evidence(chosen)
    log_line(
        f"5.8 employee={chosen} refs={compression['references_kept']} "
        f"size {compression['full_len']}->{compression['compact_len']} "
        f"({compression['size_reduction_pct']})"
    )

    # 5.9 -----------------------------------------------------------------
    specialists = ops.build_specialist_contexts()
    log_line(
        f"5.9 policy_fields={specialists['policy_field_count']} "
        f"has_email={specialists['policy_has_email']} "
        f"read_only={specialists['evidence_read_only']}"
    )

    # 5.10 ----------------------------------------------------------------
    profile = ops.build_profile(chosen)
    log_line(
        f"5.10 employee={chosen} claims={profile['claim_count']} "
        f"covered={profile['covered_skills']} missing={profile['missing_skills']}"
    )

    # 5.11 ----------------------------------------------------------------
    tampering = ops.tamper_tests(chosen)
    log_line(
        "5.11 quote_rejected={} forged_rejected={}".format(
            tampering["altered_quote"]["rejected"],
            tampering["forged_evidence_id"]["rejected"],
        )
    )

    # 5.12 ----------------------------------------------------------------
    coverage = ops.evidence_coverage()
    chart_path = out_dir / "coverage_by_department.png"
    chart_rows = ops.plot_department_coverage(chart_path)
    log_line(
        f"5.12 employees={coverage['employees']} "
        f"mean={coverage['mean_coverage']} chart={chart_path.name}"
    )
    for row in chart_rows:
        log_line(f"     {row['scope']}  mean={row['mean']}")

    results = {
        "section": 5,
        "title": "آماده‌سازی داده و مهندسی context",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "q5_1_inventory": inventory,
        "q5_2_scope": {k: v for k, v in scope.items() if k != "allowed_docs"},
        "q5_3_budget": {k: v for k, v in budget.items() if k != "selected_parts"},
        "q5_4_control": tight,
        "q5_5_retrieval": retrieval,
        "q5_6_redaction": redaction,
        "q5_7_dedupe": {k: v for k, v in dedupe.items() if k != "kept"},
        "q5_8_compression": compression,
        "q5_9_specialists": specialists,
        "q5_10_profile": profile,
        "q5_11_tamper": tampering,
        "q5_12_coverage": {k: v for k, v in coverage.items() if k != "rows"},
        "checks": {
            "ids_unique": (
                inventory["unique_ids"]["employee_id"] == inventory["people"]
                and inventory["unique_ids"]["doc_id"] == inventory["documents"]
                and inventory["unique_ids"]["request_id"] == inventory["requests"]
                and inventory["unique_ids"]["policy_scope"] == inventory["policies"]
            ),
            "splits_disjoint": all(
                v["texts"] == 0 for v in inventory["overlaps"].values()
            ),
            "scope_excludes_all_foreign": scope["scope_enforced"],
            "budget_fits": budget["remaining"] >= 0,
            "budget_rejects_oversized": tight["rejected"],
            "limit_zero_rejected": retrieval["limit_zero_rejected"],
            "email_removed": redaction["email_removed"],
            "working_text_kept": redaction["working_text_preserved"],
            "dedupe_reduced": dedupe["after"] < dedupe["before"],
            "compression_reduced": compression["compact_len"] < compression["full_len"],
            "policy_context_minimal": specialists["policy_minimal"],
            "evidence_read_only": specialists["evidence_read_only"],
            "quote_tamper_rejected": tampering["altered_quote"]["rejected"],
            "forged_ref_rejected": tampering["forged_evidence_id"]["rejected"],
            "profile_valid": tampering["baseline"]["valid"],
        },
    }

    log_line("")
    log_line("== CHECKS ==")
    for name, value in results["checks"].items():
        log_line(f"  {'ok  ' if value else 'FAIL'}  {name}")

    results_path = out_dir / "section5.json"
    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "section5_console.log").write_text("\n".join(log), encoding="utf-8")

    failed = [k for k, v in results["checks"].items() if not v]
    log_line("")
    log_line(f"results: {results_path}")
    log_line(f"failed : {failed or 'none'}")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
