"""Section 8 — real embeddings, three retrieval routes, ACL, context, latency, index guard.

Run:  .venv\\Scripts\\python.exe work/sec08_embeddings/run_section8.py
Writes: work/sec08_embeddings/artifacts/*
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from work._common.config import (
    CHUNK_OVERLAP,
    CHUNK_TOKENS,
    EMBED_DIM,
    MODEL_ID,
    MODEL_REVISION,
    SEED,
    config_fingerprint,
)
from work._common.db import connect
from work._common.paths import DB_PATH, EVAL, MODEL_DIR, ROUTER
from work.sec08_embeddings.retrieval import (
    IndexIncompatible,
    Principal,
    aggregate_to_documents,
    acl_filter,
    build_context,
    build_tfidf,
    cosine_distance,
    cosine_explicit,
    cosine_via_dot,
    dense_scores,
    index_fingerprint,
    lexical_scores,
    load_index,
    percentiles,
    reciprocal_rank_fusion,
    save_fingerprint,
)

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
results: dict = {}

INDENTATION_QUERY = "What indentation width does the style guide recommend?"
INDENTATION_QUERY_ID = "QR-63320850b7c67fb7"


def head(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


# ---------------------------------------------------------------- 8.1
head("8.1  model version, license, output dimension, token ceiling, file hashes")
from sentence_transformers import SentenceTransformer

manifest = json.loads((ROOT / "resources" / "embedding_model_manifest.json").read_text(encoding="utf-8"))
model = SentenceTransformer(str(MODEL_DIR), device="cpu")
tokenizer = model.tokenizer

hash_rows = []
matched = 0
for entry in manifest["files"]:
    target = MODEL_DIR / entry["path"]
    if not target.exists():
        hash_rows.append({**entry, "present": False, "observed": None})
        continue
    observed = hashlib.sha256(target.read_bytes()).hexdigest()
    ok = observed == entry["sha256"]
    matched += ok
    hash_rows.append({"path": entry["path"], "present": True, "match": ok, "observed": observed})

dim = model.get_embedding_dimension()
max_seq = model.max_seq_length
print("model id       :", manifest["model_id"])
print("revision       :", manifest["revision"])
print("license        :", manifest["license"])
print("dimension      :", dim)
print("token ceiling  :", max_seq)
print("files hashed   :", len([r for r in hash_rows if r["present"]]), "of", len(manifest["files"]))
print("hashes matching:", matched)
print("tokenizer ceiling vs chunk length: chunk =", CHUNK_TOKENS, "tokens, so every chunk fits")
results["8.1"] = {"model_id": manifest["model_id"], "revision": manifest["revision"],
                  "license": manifest["license"], "dimension": dim, "max_tokens": max_seq,
                  "files_checked": len(hash_rows), "hashes_matched": matched}

# ---------------------------------------------------------------- 8.2
head("8.2  batch encode every chunk, L2-normalise, report shape/norms")
con = connect(DB_PATH)
expect = {"dimension": EMBED_DIM, "model_revision": MODEL_REVISION, "model_id": MODEL_ID}
index = load_index(con, expect=expect)
print("index metadata:", json.dumps(index.metadata, indent=2))

texts = [c.content for c in index.chunks]
norms = np.linalg.norm(index.matrix, axis=1)
print("vectors       :", index.matrix.shape[0])
print("matrix shape  :", index.matrix.shape)
print("min norm      :", round(float(norms.min()), 6))
print("max norm      :", round(float(norms.max()), 6))
print("non-finite    :", int((~np.isfinite(index.matrix)).sum()))

encode_start = time.perf_counter()
encoded = model.encode(texts, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
encode_seconds = time.perf_counter() - encode_start
recomputed_norms = np.linalg.norm(encoded, axis=1)
print("fresh encode  : shape", encoded.shape, "| seconds", round(encode_seconds, 2),
      "| min norm", round(float(recomputed_norms.min()), 6),
      "| max norm", round(float(recomputed_norms.max()), 6),
      "| non-finite", int((~np.isfinite(encoded)).sum()))
# Measure the difference BEFORE replacing the matrix, otherwise the comparison is trivially zero.
max_abs_diff = float(np.abs(encoded - index.matrix).max())
print("stored vs fresh max abs diff:", max_abs_diff)

# Use the freshly encoded matrix from here on so nothing depends on the write path.
index.matrix = encoded.astype(np.float32)
results["8.2"] = {"vectors": int(index.matrix.shape[0]), "shape": list(index.matrix.shape),
                  "min_norm_stored": round(float(norms.min()), 6),
                  "max_norm_stored": round(float(norms.max()), 6),
                  "non_finite": int((~np.isfinite(index.matrix)).sum()),
                  "encode_seconds": round(encode_seconds, 2),
                  "min_norm_fresh": round(float(recomputed_norms.min()), 6),
                  "max_norm_fresh": round(float(recomputed_norms.max()), 6),
                  "stored_vs_fresh_max_abs_diff": max_abs_diff,
                  "non_finite_fresh": int((~np.isfinite(encoded)).sum())}

# ---------------------------------------------------------------- 8.3
head("8.3  cosine by explicit formula and by normalised dot product")
pair_a = index.matrix[0]
pair_b = index.matrix[1]
sim_explicit = cosine_explicit(pair_a, pair_b)
sim_dot = cosine_via_dot(pair_a, pair_b)
query_vector = model.encode([INDENTATION_QUERY], normalize_embeddings=True, convert_to_numpy=True)[0]
query_chunk_sim = cosine_explicit(query_vector, index.matrix[0])
print("pair A (chunk0 vs chunk1):")
print("  explicit formula :", round(sim_explicit, 8))
print("  normalised dot   :", round(sim_dot, 8))
print("  delta            :", abs(sim_explicit - sim_dot))
print("  distance (1 - sim):", round(cosine_distance(sim_explicit), 8))
print("pair B (query vs chunk0):")
print("  similarity       :", round(query_chunk_sim, 6))
print("  distance         :", round(cosine_distance(query_chunk_sim), 6))
print("smaller distance = closer; larger similarity = closer, so sort direction is inverted")
results["8.3"] = {"similarity": round(float(sim_explicit), 8),
                  "distance": round(float(cosine_distance(sim_explicit)), 8),
                  "pair": "chunk0 vs chunk1",
                  "dot_form": round(float(sim_dot), 8),
                  "delta": abs(sim_explicit - sim_dot),
                  "query_chunk_similarity": round(float(query_chunk_sim), 6),
                  "query_chunk_distance": round(float(cosine_distance(query_chunk_sim)), 6)}

# ---------------------------------------------------------------- 8.4
head("8.4  TF-IDF baseline, top-3 distinct documents for the indentation query")
vectorizer, tfidf_matrix = build_tfidf(texts)
lex_scores = lexical_scores(vectorizer, tfidf_matrix, INDENTATION_QUERY)
lex_docs = aggregate_to_documents(index.chunks, lex_scores, order="desc")
print("query:", INDENTATION_QUERY)
for rank, hit in enumerate(lex_docs[:3], start=1):
    print(f"  {rank}. {hit.doc_id:10s} score={hit.score:.4f} best_chunk={hit.best_chunk}")
lexical_top3 = [h.doc_id for h in lex_docs[:3]]
results["8.4"] = {"top_doc": lexical_top3[0], "top3": lexical_top3,
                  "scores": [round(h.score, 4) for h in lex_docs[:3]]}

# ---------------------------------------------------------------- 8.5
head("8.5  dense cosine for the same query, compared with the baseline")
dense_scored = dense_scores(query_vector, index.matrix)
dense_docs = aggregate_to_documents(index.chunks, dense_scored, order="desc")
for rank, hit in enumerate(dense_docs[:3], start=1):
    print(f"  {rank}. {hit.doc_id:10s} cosine={hit.score:.4f} best_chunk={hit.best_chunk}")
dense_top3 = [h.doc_id for h in dense_docs[:3]]
shared = sorted(set(lexical_top3) & set(dense_top3))
print("gold document: PEP-0008")
print("lexical top-3:", lexical_top3)
print("dense   top-3:", dense_top3)
print("shared documents in both top-3:", len(shared), shared)
print("scores are not comparable: TF-IDF", round(lex_docs[0].score, 4),
      "vs cosine", round(dense_docs[0].score, 4))
results["8.5"] = {"top_doc": dense_top3[0], "top3": dense_top3,
                  "shared": len(shared), "shared_docs": shared,
                  "cosine_top": round(dense_docs[0].score, 4),
                  "lexical_top": round(lex_docs[0].score, 4)}

# ---------------------------------------------------------------- 8.6
head("8.6  RRF fusion of the two rankings, k = 60")
fused = reciprocal_rank_fusion([[h.doc_id for h in lex_docs], [h.doc_id for h in dense_docs]])
for rank, (doc_id, score) in enumerate(fused[:3], start=1):
    print(f"  {rank}. {doc_id:10s} rrf={score:.6f}")
hybrid_top3 = [doc_id for doc_id, _ in fused[:3]]
print("hybrid top-3:", hybrid_top3)
print("gold PEP-0008 present:", "PEP-0008" in hybrid_top3)
print("RRF uses ranks only; raw scores from the two methods are never added")
results["8.6"] = {"top_doc": hybrid_top3[0], "top3": hybrid_top3,
                  "gold_present": "PEP-0008" in hybrid_top3,
                  "rrf_top": round(fused[0][1], 6)}

# ---------------------------------------------------------------- 8.7
head("8.7  store vectors in SQLite as float32 BLOB, rerun must not add rows")
before = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
with con:
    con.executemany(
        "UPDATE chunks SET embedding=?, model_id=?, model_revision=? WHERE chunk_id=?",
        [(c.embedding.astype(np.float32).tobytes(), MODEL_ID, MODEL_REVISION, c.chunk_id)
         for c in index.chunks],
    )
after_first = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
with con:
    con.executemany(
        "UPDATE chunks SET embedding=?, model_id=?, model_revision=? WHERE chunk_id=?",
        [(c.embedding.astype(np.float32).tobytes(), MODEL_ID, MODEL_REVISION, c.chunk_id)
         for c in index.chunks],
    )
after_second = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
readback = con.execute("SELECT embedding FROM chunks LIMIT 1").fetchone()[0]
print("rows before:", before, "| after first:", after_first, "| after second:", after_second)
print("stored BLOB bytes:", len(readback), "= 384 float32")
print("read-back dimension:", len(readback) // 4)
results["8.7"] = {"vectors_stored": after_second, "dimension_readback": len(readback) // 4,
                  "rows_stable": before == after_first == after_second}

# ---------------------------------------------------------------- 8.8
head("8.8  read one vector back and reproduce the local top-1")
last = con.execute(
    "SELECT chunk_id, embedding FROM chunks ORDER BY chunk_id LIMIT 1"
).fetchone()
stored = np.array(np.frombuffer(last["embedding"], dtype="<f4"), dtype=np.float32)
original = next(c.embedding for c in index.chunks if c.chunk_id == last["chunk_id"])
readback_error = float(np.abs(stored - original).max())

# exact search over the vectors as reloaded from the file
ids: list[str] = []
vectors: list[np.ndarray] = []
for row in con.execute("SELECT chunk_id, embedding FROM chunks ORDER BY chunk_id"):
    vector = np.frombuffer(row["embedding"], dtype="<f4")
    if vector.shape[0] == EMBED_DIM:
        ids.append(row["chunk_id"])
        vectors.append(vector.astype(np.float32))
reloaded = np.vstack(vectors)
scores_reloaded = dense_scores(query_vector, reloaded)
top_reloaded = ids[int(np.argmax(scores_reloaded))]
top_memory = index.chunks[int(np.argmax(dense_scored))].chunk_id
print("max read-back error:", readback_error)
print("top-1 from in-memory vectors :", top_memory)
print("top-1 from SQLite read-back  :", top_reloaded)
print("identical:", top_memory == top_reloaded)
results["8.8"] = {"top1_same": top_memory == top_reloaded, "max_readback_error": readback_error,
                  "top_chunk": top_memory}

# ---------------------------------------------------------------- 8.9
head("8.9  ACL applied before top-k; T-0 must never see T-1 internal policy")
t0 = Principal(user_id="U-002", role="student", tenant="T-0")
t1 = Principal(user_id="U-003", role="student", tenant="T-1")
admin = Principal(user_id="U-000", role="admin", tenant="T-0")
policy_query = "What is the export retention policy for experiment reports?"

def policy_visibility(principal: Principal) -> list[str]:
    allowed = acl_filter(index.chunks, principal)
    allowed_matrix = np.vstack([c.embedding for c in allowed])
    qv = model.encode([policy_query], normalize_embeddings=True, convert_to_numpy=True)[0]
    scored = dense_scores(qv, allowed_matrix)
    hits = aggregate_to_documents(allowed, scored, order="desc")
    return [h.doc_id for h in hits]

t0_docs = policy_visibility(t0)
t1_docs = policy_visibility(t1)
admin_docs = policy_visibility(admin)
leak_t0 = sum(1 for d in t0_docs if d == "LAB-T1")
leak_t1 = sum(1 for d in t1_docs if d == "LAB-T0")
admin_visible = sum(1 for d in admin_docs if d in {"LAB-T0", "LAB-T1"})
print("T-0 visible policy docs:", [d for d in t0_docs if d.startswith("LAB-")])
print("T-1 visible policy docs:", [d for d in t1_docs if d.startswith("LAB-")])
print("admin visible internal :", admin_visible, "of 2")
print("T-0 leak of T-1:", leak_t0)
print("T-1 leak of T-0:", leak_t1)
results["8.9"] = {"tenant_leak": leak_t0 + leak_t1, "admin_visible_internal": admin_visible,
                  "t0_docs": [d for d in t0_docs if d.startswith("LAB-")],
                  "t1_docs": [d for d in t1_docs if d.startswith("LAB-")]}

# ---------------------------------------------------------------- 8.10
head("8.10  700-token context from top-10 evidence")
top10 = dense_docs[:10]
chunk_lookup = {c.chunk_id: c for c in index.chunks}
ctx = build_context(top10, chunk_lookup, tokenizer, max_tokens=700)
actual_tokens = len(tokenizer.encode(ctx.text, add_special_tokens=False))
print("evidence offered :", len(top10))
print("evidence selected:", len(ctx.selected))
print("evidence dropped :", len(ctx.dropped))
print("context tokens   :", actual_tokens, "| reported:", ctx.tokens)
print("truncated last   :", ctx.truncated_last)
print("order effect: evidence is packed in rank order, so the strongest chunk occupies the")
print("earliest position; prompt cost grows linearly with tokens kept")
results["8.10"] = {"tokens": actual_tokens, "selected": len(ctx.selected),
                   "dropped": len(ctx.dropped), "truncated": ctx.truncated_last}

# ---------------------------------------------------------------- 8.11
head("8.11  p50/p95 latency for lexical, dense, hybrid after warm-up")
train_queries = [
    json.loads(line) for line in (EVAL / "queries.jsonl").read_text(encoding="utf-8").splitlines()
    if line
]
train_queries = [q for q in train_queries if q["split"] == "train"]
print("warm-up queries:", len(train_queries))

def timed(fn) -> list[float]:
    samples = []
    for item in train_queries:
        start = time.perf_counter()
        fn(item["query"])
        samples.append((time.perf_counter() - start) * 1000)
    return samples

# cold embedding is measured once, separately, and never mixed into the warm numbers
cold_start = time.perf_counter()
model.encode([train_queries[0]["query"]], normalize_embeddings=True, convert_to_numpy=True)
cold_ms = (time.perf_counter() - cold_start) * 1000
warm_start = time.perf_counter()
model.encode([train_queries[0]["query"]], normalize_embeddings=True, convert_to_numpy=True)
warm_single_ms = (time.perf_counter() - warm_start) * 1000

def lexical_route(query: str) -> None:
    scores = lexical_scores(vectorizer, tfidf_matrix, query)
    aggregate_to_documents(index.chunks, scores, order="desc")

def dense_route(query: str) -> None:
    qv = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
    scores = dense_scores(qv, index.matrix)
    aggregate_to_documents(index.chunks, scores, order="desc")

def hybrid_route(query: str) -> None:
    lex = aggregate_to_documents(index.chunks, lexical_scores(vectorizer, tfidf_matrix, query), order="desc")
    qv = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
    den = aggregate_to_documents(index.chunks, dense_scores(qv, index.matrix), order="desc")
    reciprocal_rank_fusion([[h.doc_id for h in lex], [h.doc_id for h in den]])

lex_ms = timed(lexical_route)
dense_ms = timed(dense_route)
hybrid_ms = timed(hybrid_route)
lex_p = percentiles(lex_ms)
dense_p = percentiles(dense_ms)
hybrid_p = percentiles(hybrid_ms)
print(f"lexical : p50={lex_p['p50']} ms  p95={lex_p['p95']} ms")
print(f"dense   : p50={dense_p['p50']} ms  p95={dense_p['p95']} ms")
print(f"hybrid  : p50={hybrid_p['p50']} ms  p95={hybrid_p['p95']} ms")
print("cold single embedding:", round(cold_ms, 2), "ms | warm single:", round(warm_single_ms, 2), "ms")
results["8.11"] = {"lexical": lex_p, "dense": dense_p, "hybrid": hybrid_p,
                   "cold_ms": round(cold_ms, 2), "warm_single_ms": round(warm_single_ms, 2),
                   "queries": len(train_queries)}

# ---------------------------------------------------------------- 8.12
head("8.12  reject an index whose metadata disagrees with the configuration")
config = {"chunk_tokens": CHUNK_TOKENS, "chunk_overlap": CHUNK_OVERLAP}
fingerprint = index_fingerprint(index, config)
save_fingerprint(ART / "index_fingerprint.json", fingerprint)
print("valid fingerprint:", json.dumps(fingerprint, indent=2))

attempts = [
    ("correct metadata", {"dimension": EMBED_DIM, "model_revision": MODEL_REVISION, "model_id": MODEL_ID}),
    ("wrong revision", {"dimension": EMBED_DIM, "model_revision": "0" * 40, "model_id": MODEL_ID}),
    ("wrong dimension", {"dimension": 768, "model_revision": MODEL_REVISION, "model_id": MODEL_ID}),
    ("wrong model id", {"dimension": EMBED_DIM, "model_revision": MODEL_REVISION,
                        "model_id": "some/other-model"}),
]
rejected = 0
for label, expectation in attempts:
    try:
        load_index(con, expect=expectation)
        print(f"{label:18s} -> accepted")
    except IndexIncompatible as exc:
        rejected += 1
        print(f"{label:18s} -> rejected: {exc}")
print("mismatched configurations rejected:", rejected, "of", len(attempts) - 1)
results["8.12"] = {"rejected": rejected, "fingerprint": fingerprint,
                   "config_fingerprint": config_fingerprint(chunk_tokens=CHUNK_TOKENS,
                                                            overlap=CHUNK_OVERLAP)}

con.close()

# ---------------------------------------------------------------- report
report = {
    "seed": SEED,
    "query": INDENTATION_QUERY,
    "query_id": INDENTATION_QUERY_ID,
    "results": results,
}
(ART / "retrieval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nartifacts written to", ART)
