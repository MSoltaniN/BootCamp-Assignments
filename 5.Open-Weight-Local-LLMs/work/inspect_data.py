"""Print compact structural summaries of the Day5 datasets so the docs can be precise."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parents[1] / "assignment" / "source" / "Day5"
DATA = SRC / "Day5_Datasets"


def head_csv(name: str, n: int = 3) -> None:
    p = DATA / name
    lines = p.read_text(encoding="utf-8").splitlines()
    print(f"--- {name}: {len(lines)-1} rows")
    for line in lines[: n + 1]:
        print("   ", line)


def head_jsonl(name: str, n: int = 2) -> None:
    p = DATA / name
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    print(f"--- {name}: {len(rows)} rows; keys={sorted(rows[0])}")
    for r in rows[:n]:
        print("   ", json.dumps(r, ensure_ascii=False)[:400])


def show_json(name: str) -> None:
    p = DATA / name
    obj = json.loads(p.read_text(encoding="utf-8"))
    print(f"--- {name}: {json.dumps(obj, ensure_ascii=False)[:1200]}")


def show_npz(name: str) -> None:
    p = DATA / name
    with np.load(p, allow_pickle=False) as z:
        print(f"--- {name}")
        for k in z.files:
            arr = z[k]
            print(f"    {k}: shape={arr.shape} dtype={arr.dtype}")


for f in ["model_catalog_raw.csv", "hardware_inventory.csv", "workloads.csv", "serving_requests.csv"]:
    head_csv(f)
for f in ["license_policy.json", "cost_scenarios.json"]:
    show_json(f)
for f in [
    "artifact_records.jsonl",
    "tokenizer_probes.jsonl",
    "local_eval_dev.jsonl",
    "local_eval_test.jsonl",
    "sft_records_raw.jsonl",
    "hr_policies.jsonl",
    "hr_cases.jsonl",
    "deployment_cases.jsonl",
]:
    head_jsonl(f)

for f in ["quantization_lab.npz", "adapter_lab.npz"]:
    show_npz(f)

man = json.loads((SRC / "Day5_Resources" / "resource_manifest.json").read_text(encoding="utf-8"))
print("--- resource_manifest.json")
print(json.dumps(man, ensure_ascii=False, indent=2)[:1500])

sman = json.loads((SRC / "Day5_Starter" / "student_manifest.json").read_text(encoding="utf-8"))
print("--- student_manifest.json")
print(json.dumps(sman, ensure_ascii=False, indent=2)[:2000])
