"""List every dev template once, so rule vocabulary is broadened on principle rather than by peeking."""
import pandas as pd
from pathlib import Path

df = pd.read_csv(Path("datasets/05_Router/requests.csv"))
for split in ("dev", "test"):
    print(f"\n######## {split}")
    for route in ["history", "research", "both", "unsupported"]:
        groups = df[(df["split"] == split) & (df["route"] == route)]["template_group"].unique()
        print(f"=== {route}")
        for group in groups:
            print("   ", df[df["template_group"] == group].iloc[0]["query"])
