"""Print every number the section 6-12 form needs (ASCII-safe)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
r = json.loads((ROOT / "Day4_Run_Output" / "sections_6_12.json").read_text(encoding="utf-8"))

s6, s7, s8 = r["section6"], r["section7"], r["section8"]
s9, s10, s11, s12 = r["section9"], r["section10"], r["section11"], r["section12"]

print("=== SECTION 6 ===")
print("req fields", s6["required_fields"], "addProps", s6["additional_properties_blocked"])
print("dispatch", s6["dispatcher"])
print("invalid", s6["invalid_inputs"])
print("cross", s6["cross_scope"])
print("mcp", s6["mcp"])
print("errshape", s6["error_shape"])
print("outputs", s6["model_outputs"])
print("fp", s6["fingerprint"])
print("decision", s6["decision_model"])
print("attach", s6["attachment"])

print("\n=== SECTION 7 ===")
for k in ("action_union", "normal_run", "repetition", "step_cap", "budget",
          "deadline", "retry", "retry_401", "malicious", "final_scope",
          "trajectory", "acceptance"):
    print(k, s7[k])

print("\n=== SECTION 8 ===")
print("bootstrap", s8["bootstrap"])
print("ttl", s8["ttl"])
print("durability", s8["durability"])
print("poison", s8["memory_poisoning"])
print("isolation", s8["tenant_isolation"])
print("candidates", s8["candidates"])
print("interrupt", s8["interrupt"])
print("resume", s8["resume"])
print("replay", s8["replay"])
print("binding", s8["approval_binding"])
print("rejection", s8["rejection"])
print("final", {k: v for k, v in s8["final"].items() if k != "checkpoint_schema"})
print("ckpt tables", s8["final"]["checkpoint_schema"]["tables"])

print("\n=== SECTION 9 ===")
print("labels", s9["labels"])
print("baseline", s9["baseline"])
print("selection", s9["selection"])
print("threshold", s9["threshold"])
print("testpreds", s9["test_predictions"])
print("chaining", s9["chaining"])
print("parallel", s9["parallel"])
print("coordinator", s9["coordinator"])
print("evaluator", s9["evaluator"])
print("hmac", s9["hmac"])
print("maker", s9["maker_checker"])
print("handoff", s9["handoff"])
print("timing", s9["timing"])

print("\n=== SECTION 10 ===")
print("inventory", {k: v for k, v in s10["inventory"].items() if k != "assets"})
print("detector", s10["detector"])
print("checks", {k: v for k, v in s10["checks"].items() if k != "detail"})

print("\n=== SECTION 11 ===")
print("paired", s11["paired"])
print("dev", s11["dev_rates"])
print("boot", s11["bootstrap"])
print("wall", s11["wall"])
print("cost", s11["cost"])
print("toolacc", s11["tool_accuracy"])
print("auditgroups", s11["audit_groups"])
print("logq", s11["log_quality"])
print("preds", s11["predictions"])
print("js", s11["js"])

print("\n=== SECTION 12 ===")
print("gate", s12["gate"])
print("canary", s12["canary"])
print("shadow", s12["shadow"])
print("jobs", s12["jobs"])
print("card", {k: v for k, v in s12["agent_card"].items() if k != "card"})
print("manifest", {k: v for k, v in s12["manifest"].items() if k != "files"})
print("weights", s12["weights"])
print("scope", s12["execution_scope"])
print("incident", s12["incident"])
print("integrity", s12["data_integrity"])
print("security", s12["security_controls"])
print("practical", s12["practical_answers"], "preds", s12["test_predictions"])
print("handoff", r["handoff_check"])
