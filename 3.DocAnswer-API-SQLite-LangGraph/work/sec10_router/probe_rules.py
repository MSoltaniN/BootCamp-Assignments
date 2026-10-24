"""Quick check of the rule baseline on train and dev before running the full section."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from work.sec10_router.router import accuracy, macro_f1, rule_matrix

df = pd.read_csv(ROOT / "datasets" / "05_Router" / "requests.csv")
for split in ("train", "dev"):
    frame = df[df["split"] == split]
    predicted = list(rule_matrix(frame["query"].tolist()))
    truth = frame["route"].tolist()
    print(f"{split:5s} accuracy={accuracy(truth, predicted)} macro_f1={macro_f1(truth, predicted)}")
    mismatch = [(t, p, q) for t, p, q in zip(truth, predicted, frame["query"]) if t != p]
    print(f"  mismatches: {len(mismatch)}")
    for truth_label, predicted_label, query in mismatch[:6]:
        print(f"    {truth_label:11s} -> {predicted_label:11s}  {query}")
