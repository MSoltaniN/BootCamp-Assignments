"""Section 11 metrics over the synthetic fixture logs.

The logs are fixtures, not live runs. Every function here says so implicitly by
operating only on `runs.csv` / `spans.csv`, and the report states it explicitly.

Two traps this module guards against:
  * wall time is max(end) - min(start); summing span durations double-counts
    parallel workers
  * conditional accuracy with no accepted samples is `None`, not 0
"""

from __future__ import annotations

from collections import defaultdict


def paired_summary(runs: list[dict]) -> dict:
    """Confirm each scenario carries both variants before any comparison."""
    by_scenario: dict[str, set[str]] = defaultdict(set)
    for row in runs:
        by_scenario[row["scenario_id"]].add(row["variant"])

    sizes = {len(v) for v in by_scenario.values()}
    return {
        "runs": len(runs),
        "scenarios": len(by_scenario),
        "variants": sorted({r["variant"] for r in runs}),
        "variants_per_scenario": sorted(sizes),
        "paired": sizes == {2},
        "splits": sorted({r["split"] for r in runs}),
    }


def variant_rates(runs: list[dict], split: str) -> dict:
    """Success and violation rates per variant, restricted to one split."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in runs:
        if row["split"] == split:
            grouped[row["variant"]].append(row)

    out: dict[str, dict] = {}
    for variant, rows in sorted(grouped.items()):
        total = len(rows)
        success = sum(1 for r in rows if r["success"])
        violation = sum(1 for r in rows if r["policy_violation"])
        both = sum(1 for r in rows if r["success"] and r["policy_violation"])
        edits = sum(1 for r in rows if r["human_edit"])
        out[variant] = {
            "n": total,
            "success_rate": round(success / total, 6),
            "violation_rate": round(violation / total, 6),
            "success_with_violation": both,
            "clean_success_rate": round((success - both) / total, 6),
            "human_edit_rate": round(edits / total, 6),
        }
    return out


def paired_bootstrap(runs: list[dict], split: str, iterations: int = 2000,
                     seed: int = 20261016) -> dict:
    """Paired bootstrap of the success-rate difference on one split."""
    import random

    by_scenario: dict[str, dict[str, bool]] = defaultdict(dict)
    for row in runs:
        if row["split"] == split:
            by_scenario[row["scenario_id"]][row["variant"]] = row["success"]

    pairs = [
        (v["baseline"], v["candidate"])
        for v in by_scenario.values()
        if "baseline" in v and "candidate" in v
    ]
    if not pairs:
        return {"error": "no complete pairs"}

    observed = sum(b - a for a, b in pairs) / len(pairs)

    rng = random.Random(seed)
    samples = []
    for _ in range(iterations):
        draw = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        samples.append(sum(b - a for a, b in draw) / len(pairs))
    samples.sort()

    low = samples[int(0.025 * len(samples))]
    high = samples[int(0.975 * len(samples)) - 1]

    return {
        "split": split,
        "pairs": len(pairs),
        "iterations": iterations,
        "seed": seed,
        "observed_diff": round(observed, 6),
        "ci_low": round(low, 6),
        "ci_high": round(high, 6),
        "significant": not (low <= 0 <= high),
    }


def wall_time_analysis(runs: list[dict], spans: list[dict]) -> dict:
    """Compare span-derived wall time with the recorded run duration."""
    by_run: dict[str, list[dict]] = defaultdict(list)
    for span in spans:
        by_run[span["run_id"]].append(span)

    wall: list[int] = []
    work: list[int] = []
    mismatches = 0
    work_gt_wall = 0

    recorded = {r["run_id"]: r["duration_ms"] for r in runs}

    for run_id, items in by_run.items():
        start = min(s["start_ms"] for s in items)
        end = max(s["end_ms"] for s in items)
        span_wall = end - start
        span_work = sum(s["duration_ms"] for s in items)

        wall.append(span_wall)
        work.append(span_work)

        if span_work > span_wall:
            work_gt_wall += 1
        if run_id in recorded and abs(recorded[run_id] - span_wall) > 1:
            mismatches += 1

    def percentile(values: list[int], pct: float) -> int:
        ordered = sorted(values)
        if not ordered:
            return 0
        index = int(round((pct / 100) * (len(ordered) - 1)))
        return ordered[index]

    return {
        "runs_with_spans": len(by_run),
        "p50_wall_ms": percentile(wall, 50),
        "p95_wall_ms": percentile(wall, 95),
        "mean_work_ms": round(sum(work) / len(work), 2) if work else 0,
        "mismatches_vs_recorded": mismatches,
        "work_exceeds_wall": work_gt_wall,
        "max_work_ms": max(work) if work else 0,
    }


def cost_analysis(runs: list[dict], prices: list[dict]) -> dict:
    price = prices[0]
    input_rate = price["input_usd_per_million"]
    output_rate = price["output_usd_per_million"]

    per_variant: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "runs": 0, "success": 0})
    total = 0.0

    for row in runs:
        cost = (
            row["input_tokens"] / 1_000_000 * input_rate
            + row["output_tokens"] / 1_000_000 * output_rate
        )
        total += cost
        bucket = per_variant[row["variant"]]
        bucket["cost"] += cost
        bucket["runs"] += 1
        bucket["success"] += 1 if row["success"] else 0

    detail = {
        variant: {
            "cost_usd": round(b["cost"], 6),
            "runs": b["runs"],
            "cost_per_success_usd": (
                round(b["cost"] / b["success"], 6) if b["success"] else None
            ),
        }
        for variant, b in sorted(per_variant.items())
    }

    candidate = detail.get("candidate", {})
    return {
        "model": price["model"],
        "unit": "USD",
        "total_cost_usd": round(total, 6),
        "per_variant": detail,
        "candidate_cost_per_success_usd": candidate.get("cost_per_success_usd"),
    }


def tool_accuracy(runs: list[dict]) -> dict:
    """Weighted accuracy vs mean-of-ratios, and why they differ."""
    total_calls = sum(r["tool_calls"] for r in runs)
    total_correct = sum(r["correct_calls"] for r in runs)
    weighted = total_correct / total_calls if total_calls else None

    ratios = [
        r["correct_calls"] / r["tool_calls"]
        for r in runs
        if r["tool_calls"]
    ]
    mean_ratio = sum(ratios) / len(ratios) if ratios else None

    return {
        "weighted_accuracy": None if weighted is None else round(weighted, 6),
        "mean_per_run_accuracy": None if mean_ratio is None else round(mean_ratio, 6),
        "runs": len(runs),
        "total_calls": total_calls,
        "difference": (
            None if weighted is None or mean_ratio is None
            else round(mean_ratio - weighted, 6)
        ),
        "note": (
            "mean-of-ratios weights a 1-call run the same as a 10-call run, "
            "so it is pulled up by small runs; the weighted form is the honest aggregate"
        ),
    }


def audit_group_view(runs: list[dict], groups: dict[str, str]) -> dict:
    """Attach audit groups for evaluation only -- never as a model feature."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in runs:
        if row["variant"] != "candidate":
            continue
        group = groups.get(row["employee_id"])
        if group:
            grouped[group].append(row)

    detail = {}
    for group, rows in sorted(grouped.items()):
        detail[group] = {
            "n": len(rows),
            "success_rate": round(sum(1 for r in rows if r["success"]) / len(rows), 6),
        }

    rates = [v["success_rate"] for v in detail.values()]
    return {
        "groups": detail,
        "sizes": {k: v["n"] for k, v in detail.items()},
        "max_rate": max(rates) if rates else None,
        "min_rate": min(rates) if rates else None,
        "spread": round(max(rates) - min(rates), 6) if rates else None,
    }


def log_quality(runs: list[dict], spans: list[dict]) -> dict:
    """Four structural checks on the fixture logs."""
    run_ids = [r["run_id"] for r in runs]
    unique_runs = len(set(run_ids)) == len(run_ids)

    span_ids = [s["span_id"] for s in spans]
    unique_spans = len(set(span_ids)) == len(span_ids)

    spans_link = all(s["run_id"] in set(run_ids) for s in spans)
    non_negative = all(s["end_ms"] >= s["start_ms"] for s in spans)
    calls_ok = all(r["correct_calls"] <= r["tool_calls"] for r in runs)

    checks = {
        "unique_run_ids": unique_runs,
        "unique_span_ids": unique_spans,
        "spans_link_to_runs": spans_link,
        "non_negative_intervals": non_negative,
        "correct_le_tool_calls": calls_ok,
    }
    return {
        "checks": checks,
        "passed": sum(1 for v in checks.values() if v),
        "total": len(checks),
    }


__all__ = [
    "paired_summary", "variant_rates", "paired_bootstrap", "wall_time_analysis",
    "cost_analysis", "tool_accuracy", "audit_group_view", "log_quality",
]
