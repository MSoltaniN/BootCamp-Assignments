"""Inspect the evaluation queries to find the 'indentation' question named in 8.4 and 8.5."""
import json
from pathlib import Path

q_path = Path("datasets/02_Evaluation/queries.jsonl")
rel_path = Path("datasets/02_Evaluation/qrels_train_dev.jsonl")

queries = [json.loads(line) for line in q_path.read_text(encoding="utf-8").splitlines() if line]
rels = [json.loads(line) for line in rel_path.read_text(encoding="utf-8").splitlines() if line]
print("queries:", len(queries), "| qrels:", len(rels))
print("first query:", json.dumps(queries[0], ensure_ascii=False))
print("first qrel :", json.dumps(rels[0], ensure_ascii=False)[:400])

hits = [q for q in queries if "indent" in q["query"].lower()]
print("\nqueries mentioning indentation:", len(hits))
for h in hits:
    print(json.dumps(h, ensure_ascii=False))

rel_by_id = {r["query_id"]: r for r in rels}
for h in hits:
    r = rel_by_id.get(h["query_id"])
    print("\nqrel for", h["query_id"], ":", json.dumps(r, ensure_ascii=False) if r else "not in public qrels")

splits = {}
for q in queries:
    splits[q["split"]] = splits.get(q["split"], 0) + 1
print("\nsplit counts:", splits)
