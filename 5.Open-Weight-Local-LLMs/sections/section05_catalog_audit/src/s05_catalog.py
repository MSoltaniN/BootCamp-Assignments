"""Section 5 — catalog and supply-chain audit (questions 5.1 - 5.12).

Reads only synthetic fixtures from Day5_Datasets. No model is loaded, no
pickle artifact is deserialized: `untrusted_model.bin` is hashed as raw bytes.

Run:
    .venv\\Scripts\\python.exe sections\\section05_catalog_audit\\src\\s05_catalog.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.day5 import (  # noqa: E402
    DATA,
    MODEL_HASHES,
    MODEL_REVISION,
    OUT,
    RESOURCES,
    read_json,
    read_jsonl,
    sha256_file,
    write_json,
)

SECTION = "section05_catalog_audit"
M04 = "M04"


def q51_q52_catalog():
    """5.1 grain + counts, 5.2 dedupe and uniqueness assertion."""
    import csv

    with (DATA / "model_catalog_raw.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    ids = [r["model_id"] for r in rows]
    unique_ids = sorted(set(ids))

    seen: dict[str, dict] = {}
    duplicates: list[str] = []
    conflicts: list[str] = []
    for row in rows:
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if row["model_id"] in seen:
            if json.dumps(seen[row["model_id"]], sort_keys=True, ensure_ascii=False) == key:
                duplicates.append(row["model_id"])
            else:
                conflicts.append(row["model_id"])
        else:
            seen[row["model_id"]] = row

    assert not conflicts, f"conflicting rows for the same model_id: {conflicts}"

    clean = [seen[i] for i in unique_ids]
    out_csv = OUT / "model_catalog_clean.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(clean)

    clean_ids = [r["model_id"] for r in clean]
    return {
        "raw_rows": len(rows),
        "unique_models": len(unique_ids),
        "full_duplicate": len(duplicates),
        "duplicate_ids": duplicates,
        "clean_rows": len(clean),
        # only the deduped file must be unique; the raw file is expected to have a repeat
        "ids_unique": len(clean_ids) == len(set(clean_ids)) == len(unique_ids),
        "clean_csv": str(out_csv.relative_to(OUT.parent)),
        "clean_sha256": sha256_file(out_csv),
        "rows": clean,
    }


def q53_license_status(rows: list[dict]) -> dict:
    policy = read_json(DATA / "license_policy.json")
    allow, review, deny = set(policy["auto_allow"]), set(policy["review"]), set(policy["deny"])
    statuses = {}
    for row in rows:
        lic = (row["license_id"] or "").strip()
        verified = row["publisher_verified"].strip().lower() == "true"
        if not lic:
            statuses[row["model_id"]] = policy["missing"]
        elif lic in deny:
            statuses[row["model_id"]] = "deny"
        elif lic in review:
            statuses[row["model_id"]] = "review"
        elif lic in allow:
            statuses[row["model_id"]] = "allow" if verified else "review"
        else:
            statuses[row["model_id"]] = "review"
    counts = {k: sum(1 for v in statuses.values() if v == k) for k in ("allow", "review", "deny")}
    return {"policy_id": policy["policy_id"], "statuses": statuses, "counts": counts}


def q54_name_analysis(rows: list[dict]) -> dict:
    with_a = [r["name"] for r in rows if re.search(r"-A\d+B", r["name"], re.IGNORECASE)]
    m04 = next(r for r in rows if r["model_id"] == M04)
    ratio = float(m04["active_b"]) / float(m04["total_b"])
    kinds = {}
    for r in rows:
        name = r["name"]
        if "Thinking" in name:
            kinds[r["model_id"]] = "Thinking"
        elif "Instruct" in name:
            kinds[r["model_id"]] = "Instruct"
        elif "Base" in name:
            kinds[r["model_id"]] = "Base"
        else:
            kinds[r["model_id"]] = "other"
    return {"names_with_a": with_a, "count_with_a": len(with_a), "m04_active_over_total": ratio,
            "kind_by_id": kinds}


def q55_candidates(rows: list[dict], statuses: dict) -> dict:
    cands = [
        r["model_id"] for r in rows
        if r["task"] == "generation"
        and r["instruct"].strip().lower() == "true"
        and int(r["context_limit"]) >= 32768
        and statuses.get(r["model_id"]) == "allow"
    ]
    return {"candidates": cands, "count": len(cands)}


def q56_artifacts() -> dict:
    records = read_jsonl(DATA / "artifact_records.jsonl")
    details = []
    accepted = []
    for rec in records:
        path = DATA / "artifact_samples" / rec["artifact"]
        actual = sha256_file(path)
        matches = actual == rec["expected_sha256"]
        ok = rec["trusted"] and rec["format"] == "safetensors" and matches
        details.append({"artifact": rec["artifact"], "format": rec["format"],
                        "trusted": rec["trusted"], "expected_sha256": rec["expected_sha256"],
                        "actual_sha256": actual, "hash_match": matches, "admitted": ok})
        if ok:
            accepted.append(rec["artifact"])
    return {"records": details, "accepted": accepted,
            "hash_failures": [d["artifact"] for d in details if not d["hash_match"]]}


def q57_resources() -> dict:
    manifest = read_json(RESOURCES / "resource_manifest.json")
    matches, checked = 0, []
    for entry in manifest["files"]:
        if not entry["path"].endswith(".gguf"):
            continue
        # manifest paths are relative to the Day5 bundle root, e.g. "Day5_Resources/models/x.gguf"
        p = RESOURCES.parent / entry["path"]
        if not p.exists():
            checked.append({"path": entry["path"], "present": False})
            continue
        actual = sha256_file(p)
        ok = actual == entry["sha256"] and p.stat().st_size == entry["bytes"]
        checked.append({"path": entry["path"], "present": True, "sha256": actual, "match": ok})
        matches += int(ok)
    return {"model_revision": manifest["model_revision"], "runtime_release": manifest["runtime_release"],
            "gguf_checked": checked, "gguf_matches": matches, "expected_matches": len(MODEL_HASHES)}


def q58_dataset_manifest() -> dict:
    manifest = read_json(DATA / "dataset_manifest.json")
    entries = manifest.get("files", manifest if isinstance(manifest, list) else [])
    matches, total_bytes, count = 0, 0, 0
    failures = []
    for entry in entries:
        rel = entry["path"]
        if rel.endswith("dataset_manifest.json"):
            continue
        p = DATA / rel
        if not p.exists():
            failures.append({"path": rel, "reason": "missing"})
            continue
        count += 1
        total_bytes += p.stat().st_size
        if sha256_file(p) == entry["sha256"] and p.stat().st_size == entry["bytes"]:
            matches += 1
        else:
            failures.append({"path": rel, "reason": "hash_or_size_mismatch"})
    return {"files": count, "total_bytes": total_bytes, "matches": matches,
            "all_match": matches == count and not failures, "failures": failures}


def q59_active_ratio_chart(rows: list[dict]) -> dict:
    ratios = {r["model_id"]: float(r["active_b"]) / float(r["total_b"]) for r in rows}
    moe = {k: v for k, v in ratios.items() if v < 1.0}
    lo_id = min(moe, key=moe.get)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 4.2))
        ids = list(ratios)
        vals = [ratios[i] for i in ids]
        colors = ["#22d3ee" if ratios[i] < 1 else "#94a3b8" for i in ids]
        ax.bar(ids, vals, color=colors)
        ax.axhline(1.0, color="#ef4444", ls="--", lw=1, label="Dense baseline = 1.0")
        ax.set_ylabel("active / total parameters")
        ax.set_title("Section 5.9 - active vs total parameter ratio")
        ax.set_ylim(0, 1.15)
        ax.legend()
        for i, v in zip(ids, vals):
            ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=7)
        fig.tight_layout()
        p = OUT.parent / "sections" / SECTION / "out" / "active_ratio.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=140)
        plt.close(fig)
        chart = str(p.relative_to(OUT.parent))
    except Exception as exc:  # pragma: no cover - charting is best effort
        chart = f"chart skipped: {exc}"
    return {"ratios": ratios, "min_ratio": moe[lo_id], "min_id": lo_id, "chart": chart}


def q510_model_card(rows: list[dict], statuses: dict) -> dict:
    m04 = next(r for r in rows if r["model_id"] == M04)
    card = {
        "model_id": M04,
        "name": m04["name"],
        "architecture": m04["architecture"],
        "total_b": float(m04["total_b"]),
        "active_b": float(m04["active_b"]),
        "license_snapshot": m04["license_id"],
        "license_status": statuses[M04],
        "publisher_verified": m04["publisher_verified"].strip().lower() == "true",
        "provenance": "synthetic fixture (fixture-r4) - not a real model card",
        "allowed_use": [
            "offline capacity and cost planning on this artificial catalog",
            "evaluation harness development against public dev split",
        ],
        "limitations": [
            "synthetic catalog row, no upstream repository or commit exists",
            "no Persian benchmark has been run for this entry",
            "context_limit 65536 is a fixture value, not a measured limit",
        ],
        "requires_persian_evaluation": True,
        "requires_capacity_gate": True,
        "evaluation_required": True,
    }
    write_json(OUT / "model_card_M04.json", card)
    return {"keys": len(card), "card_path": "Day5_Run_Output/model_card_M04.json",
            "evaluation_required": card["evaluation_required"]}


def q511_acceptance_plan() -> dict:
    plan = {
        "plan_id": "day5-acceptance-v1",
        "stage1_gate": {
            "name": "capacity_and_license",
            "criteria": [
                {"metric": "fits_in_memory", "unit": "boolean",
                 "method": "total_gib <= capacity_gib - reserved_gib for the target hardware"},
                {"metric": "license_status", "unit": "enum(allow/review/deny)",
                 "method": "apply license_policy.json to license_id and publisher_verified"},
                {"metric": "artifact_hash_match", "unit": "boolean",
                 "method": "sha256 of the downloaded file equals the pinned value"},
            ],
        },
        "stage2_gate": {
            "name": "semantic_quality_security_latency",
            "criteria": [
                {"metric": "dev_semantic_accuracy", "unit": "ratio 0..1",
                 "method": "compare predicted_days with expected_days on local_eval_dev.jsonl"},
                {"metric": "schema_validity", "unit": "ratio 0..1",
                 "method": "json parse of raw must equal {'days': int} for every dev case"},
                {"metric": "cross_tenant_blocked", "unit": "boolean",
                 "method": "dispatcher probe with a foreign tenant must be rejected"},
                {"metric": "client_p95_latency", "unit": "seconds",
                 "method": "client-clock wall time per request, linear-interpolation P95"},
                {"metric": "client_output_throughput", "unit": "tokens/second",
                 "method": "sum completion_tokens divided by sum elapsed_s"},
            ],
        },
        "decision_rule": "admit only if every stage1 criterion passes and every stage2 criterion meets its threshold",
        "note": "thresholds are fixed on dev before any test run; test split is never used to set them",
    }
    write_json(OUT / "acceptance_plan.json", plan)
    return {"stage1_criteria": len(plan["stage1_gate"]["criteria"]),
            "stage2_criteria": len(plan["stage2_gate"]["criteria"]),
            "path": "Day5_Run_Output/acceptance_plan.json"}


def q512_provenance(clean_sha: str, clean_rows: int) -> dict:
    import platform

    cats = sorted((DATA / "model_catalog_raw.csv").read_text(encoding="utf-8").splitlines())
    provenance = {
        "assignment": "day5",
        "section": 5,
        "seed": 20261017,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "catalog_source": "Day5_Datasets/model_catalog_raw.csv",
        "catalog_source_sha256": sha256_file(DATA / "model_catalog_raw.csv"),
        "catalog_clean": "Day5_Run_Output/model_catalog_clean.csv",
        "catalog_clean_sha256": clean_sha,
        "catalog_clean_rows": clean_rows,
        "catalog_raw_sorted_sha256": hashlib.sha256("\n".join(cats).encode()).hexdigest(),
        "model_revision": MODEL_REVISION,
        "engine_release": "b11696",
        "datasets_manifest_sha256": sha256_file(DATA / "dataset_manifest.json"),
        "all_catalog_models_executed": False,
        "executed_models": ["qwen2.5-0.5b-instruct-q4_k_m", "qwen2.5-0.5b-instruct-q8_0"],
        "execution_scope_note": (
            "Only the two pinned Qwen2.5-0.5B-Instruct GGUF files were executed. "
            "The 12 catalog entries are synthetic fixtures and none of them was run."
        ),
        "planned_real_version": "the real deployment candidate must be re-pinned to an upstream commit",
    }
    write_json(OUT / "provenance.json", provenance)
    return provenance


def main() -> int:
    cat = q51_q52_catalog()
    rows = cat["rows"]
    lic = q53_license_status(rows)
    names = q54_name_analysis(rows)
    cands = q55_candidates(rows, lic["statuses"])
    artifacts = q56_artifacts()
    resources = q57_resources()
    datasets = q58_dataset_manifest()
    ratio = q59_active_ratio_chart(rows)
    card = q510_model_card(rows, lic["statuses"])
    plan = q511_acceptance_plan()
    prov = q512_provenance(cat["clean_sha256"], cat["clean_rows"])

    summary = {
        "5.1_raw_rows": cat["raw_rows"],
        "5.1_unique_models": cat["unique_models"],
        "5.1_full_duplicate": cat["full_duplicate"],
        "5.2_clean_rows": cat["clean_rows"],
        "5.2_ids_unique": cat["ids_unique"],
        "5.3_allow": lic["counts"]["allow"],
        "5.3_review": lic["counts"]["review"],
        "5.3_deny": lic["counts"]["deny"],
        "5.4_names_with_a": names["count_with_a"],
        "5.4_m04_active_ratio": round(names["m04_active_over_total"], 6),
        "5.5_candidates": cands["candidates"],
        "5.5_candidate_count": cands["count"],
        "5.6_accepted": artifacts["accepted"],
        "5.6_hash_failures": artifacts["hash_failures"],
        "5.7_model_revision": resources["model_revision"],
        "5.7_engine_release": resources["runtime_release"],
        "5.7_gguf_matches": f'{resources["gguf_matches"]}/{resources["expected_matches"]}',
        "5.8_files": datasets["files"],
        "5.8_total_bytes": datasets["total_bytes"],
        "5.8_all_match": datasets["all_match"],
        "5.9_min_ratio": round(ratio["min_ratio"], 6),
        "5.9_min_id": ratio["min_id"],
        "5.10_card_keys": card["keys"],
        "5.11_stage2_criteria": plan["stage2_criteria"],
        "5.12_all_models_executed": prov["all_catalog_models_executed"],
    }
    write_json(OUT.parent / "sections" / SECTION / "out" / "summary.json", summary)
    write_json(OUT / "catalog_status.json", {"license": lic, "names": names, "candidates": cands,
                                            "artifacts": artifacts, "resources": resources,
                                            "datasets": datasets, "ratio": ratio, "card": card})

    print("== Section 5 summary ==")
    for key, value in summary.items():
        print(f"  {key:<28} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
