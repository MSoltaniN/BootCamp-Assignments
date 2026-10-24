"""Pre-flight inventory for «تکلیف ۳».

Reads every dataset once, verifies the corpus SHA-256 against the manifest, and
writes `artifacts/data_inventory.json` plus a readable table on stdout.

This is groundwork only: it answers the "how much data do I actually have?"
questions (5.1, 7.1, 9.1, 10.1, 12.6) before any model or database is built.
Nothing here is a graded answer; the graded numbers must come from the notebook.

    python scripts/inventory.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets"
OUT = ROOT / "artifacts" / "data_inventory.json"

SEED = 20261015  # reference seed fixed by the assignment


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def corpus_block() -> dict:
    rows = read_csv(DATA / "01_Corpus" / "manifest.csv")
    verified, mismatched, missing = [], [], []
    for row in rows:
        p = DATA / "01_Corpus" / row["path"]
        if not p.exists():
            missing.append(row["doc_id"])
        elif sha256_file(p) == row["sha256"]:
            verified.append(row["doc_id"])
        else:
            mismatched.append(row["doc_id"])
    commit = json.loads((DATA / "01_Corpus" / "source_commit.json").read_text(encoding="utf-8"))
    pdfs = sorted((DATA / "01_Corpus" / "pdf_fixtures").glob("*.pdf"))
    versions = sorted({r["version"] for r in rows})
    return {
        "documents_in_manifest": len(rows),
        "sha256_verified": len(verified),
        "sha256_mismatched": mismatched,
        "files_missing": missing,
        "distinct_versions": versions,
        "source_commit": commit.get("commit") or commit.get("revision"),
        "source_repository": commit.get("repository"),
        "pdf_fixtures": [{"name": p.name, "bytes": p.stat().st_size} for p in pdfs],
        "raw_bytes": sum(p.stat().st_size for p in (DATA / "01_Corpus" / "raw").glob("*.rst")),
    }


def evaluation_block() -> dict:
    queries = read_jsonl(DATA / "02_Evaluation" / "queries.jsonl")
    qrels = read_jsonl(DATA / "02_Evaluation" / "qrels_train_dev.jsonl")
    by_split = Counter(q["split"] for q in queries)
    q_by_split = Counter(q["split"] for q in qrels)
    labels = {}
    for split in ("train", "dev"):
        rows = [q for q in qrels if q["split"] == split]
        labels[split] = {
            "rows": len(rows),
            "answerable": sum(1 for r in rows if r.get("answerable")),
            "unanswerable": sum(1 for r in rows if not r.get("answerable")),
            "query_families": len({r.get("query_family") for r in rows}),
        }
    texts = [q["query"] for q in queries]
    dup_texts = len(texts) - len({t.strip().lower() for t in texts})
    labelled_ids = {r["query_id"] for r in qrels}
    return {
        "queries_total": len(queries),
        "queries_by_split": dict(sorted(by_split.items())),
        "qrels_rows_total": len(qrels),
        "qrels_by_split": dict(sorted(q_by_split.items())),
        "labels": labels,
        "test_labels_present_in_pack": "test" in q_by_split,
        "queries_without_public_label": len({q["query_id"] for q in queries} - labelled_ids),
        "exact_duplicate_query_texts": dup_texts,
    }


def application_block() -> dict:
    users = read_csv(DATA / "03_Application" / "users.csv")
    cases = read_jsonl(DATA / "03_Application" / "cases.jsonl")
    policies = read_jsonl(DATA / "03_Application" / "policies.jsonl")
    owners = Counter(c["owner_id"] for c in cases)
    return {
        "users": len(users),
        "roles": dict(Counter(u["role"] for u in users)),
        "tenants": dict(Counter(u["tenant"] for u in users)),
        "cases": len(cases),
        "distinct_case_owners": len(owners),
        "cases_per_owner_max": max(owners.values()) if owners else 0,
        "u002_cases": owners.get("U-002", 0),
        "policies": len(policies),
        "policy_doc_ids": [p["doc_id"] for p in policies],
        "policy_access": dict(Counter(p["access"] for p in policies)),
        "policy_tenants": dict(Counter(p["tenant"] for p in policies)),
    }


def api_block() -> dict:
    logs = read_csv(DATA / "04_API" / "request_logs.csv")
    ids = [r["request_id"] for r in logs]
    status = Counter(int(r["status"]) for r in logs)
    groups = {
        "client_validation_4xx": sum(v for k, v in status.items() if k in (400, 401, 403, 404, 409, 422)),
        "rate_limit_429": status.get(429, 0),
        "server_5xx": sum(v for k, v in status.items() if 500 <= k < 600),
        "success_2xx": sum(v for k, v in status.items() if 200 <= k < 300),
    }
    errors = len(logs) - groups["success_2xx"]
    retry = read_jsonl(DATA / "04_API" / "retry_scenarios.jsonl")
    provider = json.loads((DATA / "04_API" / "provider_config.json").read_text(encoding="utf-8"))
    return {
        "requests": len(logs),
        "unique_request_id": len(set(ids)),
        "duplicate_request_id": len(ids) - len(set(ids)),
        "status_distribution": {str(k): v for k, v in sorted(status.items())},
        "status_groups": groups,
        "error_rate": round(errors / len(logs), 4) if logs else None,
        "providers": dict(Counter(r["provider"] for r in logs)),
        "endpoints": dict(Counter(r["endpoint"] for r in logs)),
        "retry_scenarios": len(retry),
        "retry_scenario_names": [r["scenario"] for r in retry],
        "provider_config_keys": sorted(provider),
        "pricing_is_fictional": provider.get("pricing_is_fictional"),
    }


def router_block() -> dict:
    rows = read_csv(DATA / "05_Router" / "requests.csv")
    splits = {
        s: {
            "rows": sum(1 for r in rows if r["split"] == s),
            "template_groups": len({r["template_group"] for r in rows if r["split"] == s}),
            "routes": len({r["route"] for r in rows if r["split"] == s}),
        }
        for s in sorted({r["split"] for r in rows})
    }
    by_split = {s: {r["template_group"] for r in rows if r["split"] == s} for s in splits}
    shared = 0
    names = list(by_split)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared += len(by_split[a] & by_split[b])
    return {
        "requests": len(rows),
        "by_split": splits,
        "route_distribution": dict(sorted(Counter(r["route"] for r in rows).items())),
        "shared_template_groups_between_splits": shared,
        "distinct_template_groups": len({r["template_group"] for r in rows}),
        "majority_class_share_test": round(
            Counter(r["route"] for r in rows if r["split"] == "test").most_common(1)[0][1]
            / max(1, sum(1 for r in rows if r["split"] == "test")), 4),
    }


def robustness_block() -> dict:
    attacks = read_jsonl(DATA / "06_Robustness" / "attacks.jsonl")
    cands = read_jsonl(DATA / "06_Robustness" / "answer_candidates.jsonl")
    return {
        "attacks": len(attacks),
        "attack_types": dict(sorted(Counter(a["attack_type"] for a in attacks).items())),
        "expected_actions": dict(sorted(Counter(a["expected_action"] for a in attacks).items())),
        "answer_candidates": len(cands),
        "candidate_ids": [c["answer_id"] for c in cands],
        "candidates_claims": {c["answer_id"]: len(c.get("claims", [])) for c in cands},
    }


def observability_block() -> dict:
    events = read_jsonl(DATA / "07_Observability" / "events.jsonl")
    traces = {e["correlation_id"] for e in events}
    per_trace = Counter(e["correlation_id"] for e in events)
    secret = sum(1 for e in events if "TEST-ONLY-SECRET" in json.dumps(e, ensure_ascii=False))
    return {
        "events": len(events),
        "traces": len(traces),
        "events_per_trace_min": min(per_trace.values()) if per_trace else 0,
        "events_per_trace_max": max(per_trace.values()) if per_trace else 0,
        "event_types": dict(sorted(Counter(e["event_type"] for e in events).items())),
        "status_distribution": dict(sorted(Counter(e["status"] for e in events).items())),
        "events_containing_TEST_ONLY_SECRET": secret,
        "metadata_keys": sorted({k for e in events for k in (e.get("metadata") or {})}),
    }


def main() -> int:
    if not DATA.exists():
        print(f"datasets not found: {DATA}")
        return 2
    inventory = {
        "seed": SEED,
        "root": str(ROOT),
        "corpus": corpus_block(),
        "evaluation": evaluation_block(),
        "application": application_block(),
        "api": api_block(),
        "router": router_block(),
        "robustness": robustness_block(),
        "observability": observability_block(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    c, e, a, p, r, rb, o = (inventory[k] for k in
                            ("corpus", "evaluation", "application", "api", "router", "robustness", "observability"))
    print("index".ljust(26), "value")
    print("-" * 60)
    rows = [
        ("corpus.documents", c["documents_in_manifest"]),
        ("corpus.sha256_verified", c["sha256_verified"]),
        ("corpus.pdf_fixtures", len(c["pdf_fixtures"])),
        ("evaluation.queries", e["queries_total"]),
        ("evaluation.queries_by_split", e["queries_by_split"]),
        ("evaluation.qrels_rows", e["qrels_rows_total"]),
        ("evaluation.test_labels_public", e["test_labels_present_in_pack"]),
        ("application.users", a["users"]),
        ("application.cases", a["cases"]),
        ("application.u002_cases", a["u002_cases"]),
        ("application.policies", a["policies"]),
        ("api.requests", p["requests"]),
        ("api.unique_request_id", p["unique_request_id"]),
        ("api.error_rate", p["error_rate"]),
        ("api.retry_scenarios", p["retry_scenarios"]),
        ("router.requests", r["requests"]),
        ("router.shared_template_groups", r["shared_template_groups_between_splits"]),
        ("robustness.attacks", rb["attacks"]),
        ("robustness.answer_candidates", rb["answer_candidates"]),
        ("observability.events", o["events"]),
        ("observability.traces", o["traces"]),
    ]
    for k, v in rows:
        print(k.ljust(26), v)
    print("-" * 60)
    print("written:", OUT)
    problems = bool(c["sha256_mismatched"] or c["files_missing"])
    print("corpus integrity:", "FAIL" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
