"""Print the section-5 numbers needed for the answer form (ASCII only)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
result = json.loads((ROOT / "Day4_Run_Output" / "section5.json").read_text(encoding="utf-8"))

inv = result["q5_1_inventory"]
print("5.1 people", inv["people"], "policies", inv["policies"], "docs", inv["documents"])
print("5.1 splits", inv["splits"], "groups", inv["template_groups"])
print("5.1 overlaps", inv["overlaps"])
print("5.1 unique", inv["unique_ids"])

sc = result["q5_2_scope"]
print("5.2 allowed", sc["allowed"], "other_tenant", sc["excluded_by_other_tenant"],
      "other_dept", sc["excluded_by_other_department"], "enforced", sc["scope_enforced"])

bg = result["q5_3_budget"]
print("5.3 selected", bg["selected"], "used", bg["used"], "remaining", bg["remaining"],
      "capacity", bg["capacity"], "skipped", bg["skipped"], "util", bg["utilization"])

c4 = result["q5_4_control"]
print("5.4 rejected", c4["rejected"], "capacity", c4["capacity"], "mandatory", c4["mandatory_tokens"])

rt = result["q5_5_retrieval"]
print("5.5 retrieved", rt["retrieved"], "distinct_scores", rt["distinct_scores"])
for row in rt["top"]:
    print("      ", row["doc_id"], row["kind"], row["score"])

rd = result["q5_6_redaction"]
print("5.6 emails", rd["emails_found"], "removed", rd["email_removed"],
      "preserved", rd["working_text_preserved"], rd["original_len"], "->", rd["redacted_len"])

dd = result["q5_7_dedupe"]
print("5.7 before", dd["before"], "after", dd["after"], "removed", dd["removed"],
      "chars", dd["before_chars"], "->", dd["after_chars"], dd["char_reduction_pct"])

cp = result["q5_8_compression"]
print("5.8 refs", cp["references_kept"], "len", cp["full_len"], "->", cp["compact_len"],
      cp["size_reduction_pct"], "bytes", cp["full_len_bytes"], "->", cp["compact_len_bytes"])

sp = result["q5_9_specialists"]
print("5.9 policy_fields", sp["policy_field_count"], "policy_bytes", sp["policy_bytes"],
      "minimal", sp["policy_minimal"], "evidence_refs", sp["evidence_ref_count"],
      "evidence_bytes", sp["evidence_bytes"], "read_only", sp["evidence_read_only"])

pr = result["q5_10_profile"]
print("5.10 claims", pr["claim_count"], "decision", pr["decision"])
print("      covered", pr["covered_skills"], "missing", pr["missing_skills"])

tp = result["q5_11_tamper"]
print("5.11 quote", tp["altered_quote"]["code"], "forged", tp["forged_evidence_id"]["code"],
      "baseline", tp["baseline"])

cv = result["q5_12_coverage"]
print("5.12 mean", cv["mean_coverage"], cv["mean_coverage_pct"])
for scope, stats in cv["by_department"].items():
    print("      ", scope, stats)
