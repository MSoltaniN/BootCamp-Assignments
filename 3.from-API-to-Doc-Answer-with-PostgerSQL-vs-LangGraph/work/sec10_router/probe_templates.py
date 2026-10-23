"""Print one representative query per route and template group, to write rules from real data."""
import pandas as pd
from pathlib import Path

df = pd.read_csv(Path("datasets/05_Router/requests.csv"))
print("templates per route (train split):")
for route in ["history", "research", "both", "unsupported"]:
    groups = df[(df["split"] == "train") & (df["route"] == route)]["template_group"].unique()
    print(f"\n=== {route} ({len(groups)} groups)")
    for group in groups:
        sample = df[df["template_group"] == group].iloc[0]
        print(f"  {group:14s} {sample['query']}")
