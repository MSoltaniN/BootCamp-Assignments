"""Find the true topic vocabulary: the only part that varies inside a template group."""
from collections import Counter
import re
import pandas as pd
from pathlib import Path

df = pd.read_csv(Path("datasets/05_Router/requests.csv"))

groups = df.groupby("template_group")["query"].apply(list)
tails = Counter()
for group, queries in groups.items():
    prefixes = []
    for q in queries:
        m = re.search(r"\b(for|about|on|justify|explaining|related to)\s+(?:the\s+)?(?:claim\s+about\s+)?(.+?)\.?$", q)
        prefixes.append(m.group(2) if m else None)
    tails.update(p for p in prefixes if p)

print("candidate topics and counts:")
for topic, count in tails.most_common(30):
    print(f"  {count:4d}  {topic!r}")

print("\nrows per route/topic check: 480 rows, 4 routes, so topics should number:")
print("  120 rows per route / 12 phrasings per topic =", 120 / 12)
