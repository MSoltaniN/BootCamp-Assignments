"""Fictional cost accounting from `provider_config.json`.

Prices are per **million tokens** in the file; they are invented for the exercise
(`pricing_is_fictional: true`) and must never be presented as real vendor pricing.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "datasets" / "04_API" / "provider_config.json"


def load_pricing(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def request_cost(input_tokens: int, output_tokens: int, prices: dict) -> float:
    """Cost of one request in the config's currency (USD here)."""
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def provider_totals(rows, pricing: dict) -> dict[str, dict]:
    """Aggregate cost per provider over an iterable of log rows."""
    totals: dict[str, dict] = {}
    for row in rows:
        provider = row["provider"]
        prices = pricing.get(provider)
        if prices is None:
            continue
        bucket = totals.setdefault(
            provider, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        )
        bucket["requests"] += 1
        bucket["input_tokens"] += int(row["input_tokens"])
        bucket["output_tokens"] += int(row["output_tokens"])
        bucket["cost_usd"] += request_cost(int(row["input_tokens"]), int(row["output_tokens"]), prices)
    for bucket in totals.values():
        bucket["cost_usd"] = round(bucket["cost_usd"], 6)
    return totals
