"""Section 9 — retrieval evaluation, method lock, hidden-test predictions, abstention.

Run:  .venv\\Scripts\\python.exe work/sec09_evaluation/run_section9.py
Writes: work/sec09_evaluation/artifacts/*, deliverables/*.jsonl, artifacts/lock.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from sentence_transformers import SentenceTransformer

from work._common.config import CHUNK_OVERLAP, CHUNK_TOKENS, MODEL_ID, MODEL_REVISION, SEED, config_fingerprint
from work._common.db import connect
from work._common.paths import CORPUS_RAW, DB_PATH, EVAL, MANIFEST as CORPUS_MANIFEST, MODEL_DIR
from work.sec08_embeddings.retrieval import (
    aggregate_to_documents,
    build_tfidf,
    dense_scores,
    lexical_scores,
    load_index,
    reciprocal_rank_fusion,
)
from work.sec09_evaluation.metrics import bootstrap_ci, choose_threshold, evaluate, mrr_at_k, ndcg_at_k, recall_at_k

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
DELIV = ROOT / "deliverables"
DELIV.mkdir(exist_ok=True)
results: dict = {}
LOCK_PATH = ART / "lock.json"


def head(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


queries = load_jsonl(EVAL / "queries.jsonl")
qrels_rows = load_jsonl(EVAL / "qrels_train_dev.jsonl")
qrels = {row["query_id"]: row for row in qrels_rows}
by_split = {split: [q for q in queries if q["split"] == split] for split in ("train", "dev", "test")}

# ---------------------------------------------------------------- 9.1
head("9.1  split sizes, answerable distribution, exact duplicates")
print("queries per split:", {k: len(v) for k, v in by_split.items()})
print("public qrels rows:", len(qrels_rows))

for split in ("train", "dev"):
    entries = [qrels[q["query_id"]] for q in by_split[split] if q["query_id"] in qrels]
    answerable = sum(1 for e in entries if e["answerable"])
    print(f"  {split:5s}: {len(entries)} labelled, answerable={answerable}, "
          f"unanswerable={len(entries) - answerable}")

labelled_test = sum(1 for q in by_split["test"] if q["query_id"] in qrels)
print("test rows present in public qrels:", labelled_test, "(labels withheld by design)")

texts = [q["query"].strip().lower() for q in queries]
duplicates = sum(count - 1 for count in Counter(texts).values() if count > 1)
print("exact duplicate query texts:", duplicates)

families = Counter(r["query_family"] for r in qrels_rows)
print("distinct query families in public qrels:", len(families))
print("largest family sizes:", families.most_common(3))
results["9.1"] = {"queries": len(queries), "duplicates": duplicates,
                  "splits": {k: len(v) for k, v in by_split.items()},
                  "families": len(families)}

# ---------------------------------------------------------------- 9.2
head("9.2  Recall@3, MRR@3, nDCG@3 on two hand-checked examples")
examples = [("gold={A}, ranking=[B,A,C]", ["B", "A", "C"]),
            ("gold={A}, ranking=[B,C,D]", ["B", "C", "D"])]
table_92 = []
for label, ranking in examples:
    r = recall_at_k(ranking, ["A"], 3)
    m = mrr_at_k(ranking, ["A"], 3)
    n = ndcg_at_k(ranking, ["A"], 3)
    print(f"{label}: recall={r} mrr={round(m, 4)} ndcg={round(n, 4)}")
    table_92.append({"case": label, "recall": r, "mrr": round(m, 4), "ndcg": round(n, 4)})
print("gold A at rank 2  -> recall 1, mrr 0.5, ndcg 0.6309")
print("gold A absent     -> recall 0, mrr 0,    ndcg 0")
results["9.2"] = table_92

# ---------------------------------------------------------------- setup for 9.3 onward
model = SentenceTransformer(str(MODEL_DIR), device="cpu")
con = connect(DB_PATH)
index = load_index(con, expect={"dimension": 384, "model_revision": MODEL_REVISION, "model_id": MODEL_ID})
texts_chunks = [c.content for c in index.chunks]
vectorizer, tfidf_matrix = build_tfidf(texts_chunks)

_embedding_cache: dict[str, np.ndarray] = {}


def embed_query(text: str) -> np.ndarray:
    if text not in _embedding_cache:
        _embedding_cache[text] = model.encode([text], normalize_embeddings=True,
                                              convert_to_numpy=True)[0]
    return _embedding_cache[text]


def rank_documents(query_text: str, method: str) -> list[str]:
    lex = aggregate_to_documents(index.chunks, lexical_scores(vectorizer, tfidf_matrix, query_text), "desc")
    if method == "lexical":
        return [h.doc_id for h in lex]
    den = aggregate_to_documents(index.chunks, dense_scores(embed_query(query_text), index.matrix), "desc")
    if method == "dense":
        return [h.doc_id for h in den]
    return [doc_id for doc_id, _ in reciprocal_rank_fusion([[h.doc_id for h in lex], [h.doc_id for h in den]])]


def rank_all(split: str, method: str) -> dict[str, list[str]]:
    return {q["query_id"]: rank_documents(q["query"], method) for q in by_split[split]}


def max_dense_similarity(query_text: str) -> float:
    return float(np.max(dense_scores(embed_query(query_text), index.matrix)))


# ---------------------------------------------------------------- 9.3
head("9.3  lexical vs dense vs hybrid on dev, k=3")
dev_qrels = {qid: entry for qid, entry in qrels.items() if entry["split"] == "dev" and entry["answerable"]}
print("dev answerable queries:", len(dev_qrels))

dev_rankings = {method: rank_all("dev", method) for method in ("lexical", "dense", "hybrid")}
dev_scores = {method: evaluate(rankings, dev_qrels, k=3) for method, rankings in dev_rankings.items()}
for method, scores in dev_scores.items():
    print(f"{method:8s} recall@3={scores['recall@3']}  mrr@3={scores['mrr@3']}  ndcg@3={scores['ndcg@3']}")
results["9.3"] = {m: {k: v for k, v in s.items() if k != "per_query"} for m, s in dev_scores.items()}

# ---------------------------------------------------------------- 9.4
head("9.4  choose the method on MRR@3 only, then lock")
tie_order = ["lexical", "dense", "hybrid"]
best_method = max(tie_order, key=lambda m: (dev_scores[m]["mrr@3"], -tie_order.index(m)))
best_mrr = dev_scores[best_method]["mrr@3"]
print("MRR@3 per method:", {m: dev_scores[m]["mrr@3"] for m in tie_order})
print("tie-break order: lexical -> dense -> hybrid")
print("selected method:", best_method, "| MRR@3 on dev:", best_mrr)

config_hash = hashlib.sha256(json.dumps({
    "method": best_method, "k": 3, "seed": SEED, "model_id": MODEL_ID,
    "model_revision": MODEL_REVISION, "chunk_tokens": CHUNK_TOKENS,
    "chunk_overlap": CHUNK_OVERLAP, "rrf_k": 60,
}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
lock_payload = {
    "locked": True, "method": best_method, "mrr@3_dev": best_mrr,
    "selection_rule": "highest MRR@3 on dev; tie-break lexical, then dense, then hybrid",
    "config_hash": config_hash, "fingerprint": config_fingerprint(),
    "seed": SEED, "test_files_built": False,
}
LOCK_PATH.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")
print("lock written:", json.dumps(lock_payload, indent=2))
results["9.4"] = {"method": best_method, "mrr_dev": best_mrr, "config_hash": config_hash}

# ---------------------------------------------------------------- 9.5
head("9.5  sensitivity to k = 1, 3, 5 for the locked method")
k_rows = []
for k in (1, 3, 5):
    scores = evaluate(dev_rankings[best_method], dev_qrels, k=k)
    k_rows.append({"k": k, "recall": scores[f"recall@{k}"], "mrr": scores[f"mrr@{k}"],
                   "ndcg": scores[f"ndcg@{k}"]})
    print(f"k={k}: recall={scores[f'recall@{k}']}  mrr={scores[f'mrr@{k}']}  ndcg={scores[f'ndcg@{k}']}")
print("recall cannot decrease as k grows because it asks only whether a relevant doc is inside k")
print("mrr can move either way: a relevant doc found earlier lowers it, a newly included one raises it")
results["9.5"] = k_rows

# ---------------------------------------------------------------- 9.6
head("9.6  first three dev errors of the locked method")
locked_rankings = dev_rankings[best_method]


def best_chunk_of(doc_id: str, query_text: str) -> str:
    """Highest-scoring chunk of one document, so a passage-level check is possible."""
    qv = embed_query(query_text)
    scored = [(c.chunk_id, float(s)) for c, s in zip(index.chunks, dense_scores(qv, index.matrix))
              if c.doc_id == doc_id]
    return max(scored, key=lambda pair: pair[1])[0] if scored else ""


def chunk_text_of(chunk_id: str) -> str:
    return next((c.content for c in index.chunks if c.chunk_id == chunk_id), "")


errors = []
for qid, entry in dev_qrels.items():
    ranking = locked_rankings.get(qid, [])
    gold = set(entry["relevant_doc_ids"])
    if gold & set(ranking[:3]):
        continue

    gold_rank = next((i + 1 for i, d in enumerate(ranking) if d in gold), None)
    gold_doc = sorted(gold)[0]
    cue = (entry.get("evidence_cue") or "").strip()
    passage_has_cue = bool(cue) and cue.lower() in chunk_text_of(best_chunk_of(gold_doc, entry["query"])).lower()

    # Three distinguishable failures:
    #   document -> the gold document never appears in the ranking at all
    #   ranking  -> it appears, but outside the top-k
    #   passage  -> it was retrieved, yet its best chunk does not contain the expected evidence cue
    if gold_rank is None:
        error_type = "document"
    elif not passage_has_cue:
        error_type = "passage"
    else:
        error_type = "ranking"

    errors.append({
        "query_id": qid, "query": entry["query"], "gold": sorted(gold),
        "top1": ranking[0] if ranking else None, "gold_rank": gold_rank,
        "error_type": error_type, "evidence_cue": cue, "passage_contains_cue": passage_has_cue,
    })

print("recall@3 failures in dev:", len(errors))
if not errors:
    print("  none at k=3")
for row in errors[:3]:
    print(f"  {row['query_id']}  gold={row['gold']}  top1={row['top1']}  "
          f"gold_rank={row['gold_rank']}  type={row['error_type']}")
    print(f"     Q: {row['query']}")
    print(f"     evidence cue {row['evidence_cue']!r} in gold doc's best chunk: {row['passage_contains_cue']}")
print("error types:", dict(Counter(row["error_type"] for row in errors)))
results["9.6"] = {"errors": len(errors), "examples": errors[:3],
                  "types": dict(Counter(row["error_type"] for row in errors))}

# ---------------------------------------------------------------- 9.7
head("9.7  build test predictions after the lock")
if not LOCK_PATH.exists():
    raise SystemExit("refusing to build test predictions without the lock file")
print("lock present:", LOCK_PATH.exists(), "| config hash:", config_hash)

test_rankings = rank_all("test", best_method)
predictions = []
for q in by_split["test"]:
    ranked = test_rankings[q["query_id"]][:3]
    # three distinct documents are required; the ranking is already distinct at document level
    assert len(ranked) == 3 and len(set(ranked)) == 3
    predictions.append({"query_id": q["query_id"], "ranked_doc_ids": ranked})

pred_path = DELIV / "test_predictions.jsonl"
with pred_path.open("w", encoding="utf-8") as fh:
    for row in predictions:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
print("test predictions:", len(predictions))
print("sample:", json.dumps(predictions[0], ensure_ascii=False))
print("distinct document count per row is enforced by an assert")
results["9.7"] = {"predictions": len(predictions), "path": str(pred_path.relative_to(ROOT)),
                  "sample": predictions[0]}

# ---------------------------------------------------------------- 9.8
head("9.8  bootstrap 95% interval for Recall@3 on dev")
recall_values = [v["recall"] for v in dev_scores[best_method]["per_query"].values()]
ci = bootstrap_ci(recall_values, n_resamples=2000, seed=SEED, level=0.95)
print("per-query recall values:", len(recall_values), "| mean:", ci["mean"])
print("95% CI:", f"[{ci['low']}, {ci['high']}]", "from", ci["resamples"], "resamples")
print("caveat: several dev queries paraphrase the same source, so the interval is optimistic")
results["9.8"] = ci

# ---------------------------------------------------------------- 9.9
head("9.9  choose the abstention threshold on dev by balanced accuracy")
dev_all = [qrels[q["query_id"]] for q in by_split["dev"] if q["query_id"] in qrels]
dev_max_sim = [max_dense_similarity(entry["query"]) for entry in dev_all]
dev_labels = [bool(entry["answerable"]) for entry in dev_all]
threshold_info = choose_threshold(dev_max_sim, dev_labels)
print("dev queries scored:", len(dev_all), "| answerable:", sum(dev_labels))
print(json.dumps(threshold_info, indent=2))
results["9.9"] = threshold_info

# ---------------------------------------------------------------- 9.10
head("9.10  apply the fixed threshold to the test questions")
test_scores = [(q["query_id"], max_dense_similarity(q["query"])) for q in by_split["test"]]
decisions = [{"query_id": qid, "score": round(score, 6),
              "accepted": bool(score >= threshold_info["threshold"])} for qid, score in test_scores]
answer_path = DELIV / "answerability_predictions.jsonl"
with answer_path.open("w", encoding="utf-8") as fh:
    for row in decisions:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
accepted = sum(1 for d in decisions if d["accepted"])
print("decisions:", len(decisions), "| accepted:", accepted, "| abstained:", len(decisions) - accepted)
print("threshold used:", threshold_info["threshold"], "(chosen on dev, not on test)")
results["9.10"] = {"decisions": len(decisions), "accepted": accepted,
                   "abstained": len(decisions) - accepted,
                   "threshold": threshold_info["threshold"],
                   "path": str(answer_path.relative_to(ROOT))}

# ---------------------------------------------------------------- 9.11
head("9.11  ablation on six dev queries: 110 vs 220 token chunks (real re-chunking)")
# Re-chunk the source documents at 110 tokens instead of truncating existing chunks, so the
# vector count really changes and the index cost is comparable.
from work.sec07_ingestion.ingest import assign_ids, chunk_text, load_manifest, parse_rst

sample = [q for q in by_split["dev"] if qrels.get(q["query_id"], {}).get("answerable")][:6]
print("ablation queries:", len(sample))

manifest = load_manifest(CORPUS_MANIFEST)
docs_110: list = []
for row in manifest:
    text = (CORPUS_RAW / Path(row["path"]).name).read_text(encoding="utf-8", errors="replace")
    parsed = parse_rst(text)
    docs_110.extend(chunk_text(text, doc_id=row["doc_id"], version=row["version"],
                               tokenizer=model.tokenizer, chunk_tokens=110,
                               overlap=CHUNK_OVERLAP, section_lookup=parsed["sections"]))
assign_ids(docs_110)
print("re-chunked at 110 tokens:", len(docs_110), "chunks from", len(manifest), "documents")

matrix_110 = model.encode([c.content for c in docs_110], batch_size=64,
                          normalize_embeddings=True, convert_to_numpy=True)
chunks_110 = [type("C", (), {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "content": c.content})()
              for c in docs_110]

ablation = {}
for label, chunks, matrix in (("220-token", index.chunks, index.matrix),
                              ("110-token", chunks_110, matrix_110)):
    recalls, mrrs = [], []
    for q in sample:
        gold = set(qrels[q["query_id"]]["relevant_doc_ids"])
        ranked = [h.doc_id for h in aggregate_to_documents(
            chunks, dense_scores(embed_query(q["query"]), matrix), "desc")][:3]
        recalls.append(recall_at_k(ranked, gold, 3))
        mrrs.append(mrr_at_k(ranked, gold, 3))
    ablation[label] = {"recall@3": round(sum(recalls) / len(recalls), 4),
                       "mrr@3": round(sum(mrrs) / len(mrrs), 4),
                       "vectors": int(matrix.shape[0])}
    print(f"{label:10s} recall@3={ablation[label]['recall@3']}  mrr@3={ablation[label]['mrr@3']}  "
          f"vectors={ablation[label]['vectors']}")

ratio = ablation["110-token"]["vectors"] / ablation["220-token"]["vectors"]
print(f"vector-count ratio 110/220: {ratio:.2f}x  -> index size and retrieval cost scale the same way")
print("this ablation runs on 6 dev queries and is reported separately from the locked test result")
results["9.11"] = {"ablation": ablation, "queries": len(sample), "vector_ratio": round(ratio, 2)}

# ---------------------------------------------------------------- 9.12
head("9.12  machine-readable evaluation report")
report = {
    "schema": "day3-evaluation-report/1",
    "seed": SEED,
    "split_used_for_selection": "dev",
    "metric_level": "document",
    "metric_unit": "mean over answerable dev queries",
    "locked_method": best_method,
    "config_hash": config_hash,
    "fingerprint": config_fingerprint(),
    "dev": {m: {k: v for k, v in s.items() if k != "per_query"} for m, s in dev_scores.items()},
    "k_sensitivity": k_rows,
    "bootstrap_recall@3": ci,
    "abstention": threshold_info,
    "test_predictions": len(predictions),
    "answerability_decisions": len(decisions),
    "limitations": [
        "Only 24 labelled dev queries; every metric has wide sampling error.",
        "Several dev queries paraphrase the same source document, so they are not independent.",
        "Relevance is binary and document-level: ranking the right document with the wrong passage still counts as a hit.",
        "The test split has 30 queries and hidden labels; no score in this report describes test performance.",
        "The corpus is 24 PEP documents, which is far smaller than any realistic retrieval workload.",
        "Lexical and dense scores are on different scales; the hybrid uses rank fusion only.",
    ],
    "claims_not_supported": [
        "That this retriever is better than another system on Python documentation in general.",
        "That the dev numbers predict test performance.",
        "That semantic similarity equals answer correctness.",
    ],
}
report_path = ART / "evaluation_report.json"
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("limitations recorded:", len(report["limitations"]))
print("report written to", report_path.relative_to(ROOT))

lock_payload["test_files_built"] = True
LOCK_PATH.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")
results["9.12"] = {"limitations": len(report["limitations"]),
                   "report": str(report_path.relative_to(ROOT))}

con.close()
(ART / "section9_results.json").write_text(json.dumps({"seed": SEED, "results": results}, indent=2),
                                          encoding="utf-8")
print("\nartifacts written to", ART)
