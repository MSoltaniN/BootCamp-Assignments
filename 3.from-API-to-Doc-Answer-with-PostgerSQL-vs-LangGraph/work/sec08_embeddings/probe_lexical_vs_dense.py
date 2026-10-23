"""Evidence for why lexical still matters: where does it beat dense, and on what kind of query?

Compares rank-1 hits on dev answerable queries and prints the cases where the two disagree,
so the argument rests on this corpus rather than on intuition.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from sentence_transformers import SentenceTransformer

from work._common.db import connect
from work._common.paths import DB_PATH, EVAL, MODEL_DIR
from work.sec08_embeddings.retrieval import (
    aggregate_to_documents,
    build_tfidf,
    dense_scores,
    lexical_scores,
    load_index,
)

model = SentenceTransformer(str(MODEL_DIR), device="cpu")
con = connect(DB_PATH)
index = load_index(con)
texts = [c.content for c in index.chunks]
vectorizer, tfidf_matrix = build_tfidf(texts)

queries = [json.loads(l) for l in (EVAL / "queries.jsonl").read_text(encoding="utf-8").splitlines() if l]
qrels = {r["query_id"]: r for r in
         (json.loads(l) for l in (EVAL / "qrels_train_dev.jsonl").read_text(encoding="utf-8").splitlines() if l)}

dev_answerable = [q for q in queries if q["split"] == "dev"
                  and qrels.get(q["query_id"], {}).get("answerable")]
print("dev answerable queries:", len(dev_answerable))

lex_hits = dense_hits = both = 0
lex_only, dense_only = [], []

for q in dev_answerable:
    gold = set(qrels[q["query_id"]]["relevant_doc_ids"])
    lex_rank = [d.doc_id for d in aggregate_to_documents(
        index.chunks, lexical_scores(vectorizer, tfidf_matrix, q["query"]), order="desc")]
    qv = model.encode([q["query"]], normalize_embeddings=True, convert_to_numpy=True)[0]
    den_rank = [d.doc_id for d in aggregate_to_documents(
        index.chunks, dense_scores(qv, index.matrix), order="desc")]

    lex_ok = lex_rank[0] in gold
    den_ok = den_rank[0] in gold
    lex_hits += lex_ok
    dense_hits += den_ok
    both += lex_ok and den_ok
    if lex_ok and not den_ok:
        lex_only.append((q["query"], sorted(gold), den_rank[0]))
    if den_ok and not lex_ok:
        dense_only.append((q["query"], sorted(gold), lex_rank[0]))

print(f"rank-1 correct  -> lexical: {lex_hits}/{len(dev_answerable)}   dense: {dense_hits}/{len(dev_answerable)}   both: {both}")
print(f"\nlexical right, dense wrong ({len(lex_only)}):")
for query, gold, predicted in lex_only:
    print(f"  Q: {query}\n     gold={gold}  dense_predicted={predicted}")
print(f"\ndense right, lexical wrong ({len(dense_only)}):")
for query, gold, predicted in dense_only:
    print(f"  Q: {query}\n     gold={gold}  lexical_predicted={predicted}")

# how do the two routes handle a query made only of an exact rare identifier?
rare = "What does := do?"
qv = model.encode([rare], normalize_embeddings=True, convert_to_numpy=True)[0]
lex_top = [d.doc_id for d in aggregate_to_documents(
    index.chunks, lexical_scores(vectorizer, tfidf_matrix, rare), order="desc")][:3]
den_top = [d.doc_id for d in aggregate_to_documents(
    index.chunks, dense_scores(qv, index.matrix), order="desc")][:3]
print(f"\nexact-identifier query: {rare!r}")
print("  lexical top-3:", lex_top)
print("  dense   top-3:", den_top)
con.close()
