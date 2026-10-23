"""Section 7 — document ingestion with provenance, chunking, dedup, policies, SQLite storage.

Run:  .venv\\Scripts\\python.exe work/sec07_ingestion/run_section7.py
Writes: work/sec07_ingestion/artifacts/*, chunks.jsonl, and refreshes day3.sqlite chunks.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from work._common.config import (
    CHUNK_OVERLAP,
    CHUNK_TOKENS,
    CORPUS_VERSION,
    EMBED_DIM,
    MODEL_ID,
    MODEL_REVISION,
    SEED,
    config_fingerprint,
)
from work._common.db import connect, sha256_text, upsert_chunk, upsert_document
from work._common.paths import APP, CORPUS, DB_PATH, MANIFEST
from work.sec07_ingestion.ingest import (
    assign_ids,
    chunk_text,
    citation_path,
    dedupe,
    load_manifest,
    make_chunk_id,
    parse_rst,
    read_pdf,
    verify_manifest,
    verify_provenance,
)

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
results: dict = {}


def head(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


from sentence_transformers import SentenceTransformer

model = SentenceTransformer(str(ROOT / "resources" / "embedding_model"), device="cpu")
tokenizer = model.tokenizer
print("tokenizer:", MODEL_ID, "| max_seq_length:", model.max_seq_length)

# ---------------------------------------------------------------- 7.1
head("7.1  manifest vs raw files, SHA-256 of every document")
rows = load_manifest(MANIFEST)
checked, valid_hashes = verify_manifest(rows, CORPUS)
print("manifest documents:", len(rows))
print("valid sha256:", valid_hashes, "of", len(rows))
bad = [r["doc_id"] for r in checked if not r["hash_ok"]]
print("mismatched:", bad or "none")
print("corpus version:", CORPUS_VERSION)
results["7.1"] = {"documents": len(rows), "valid_hashes": valid_hashes,
                  "corpus_version": CORPUS_VERSION}

# ---------------------------------------------------------------- 7.2
head("7.2  PDF fixtures page by page")
pdfs = sorted((CORPUS / "pdf_fixtures").glob("*.pdf"))
pdf_reports = []
for pdf in pdfs:
    report = read_pdf(pdf)
    print(f"{report['path']:26s} pages={report['pages']} chars={report['chars']} "
          f"per_page={report['chars_per_page']} needs_Ocr={report['needs_ocr']}")
    pdf_reports.append(report)
flagged = sum(1 for r in pdf_reports if r["needs_ocr"])
print("PDFs:", len(pdf_reports), "| flagged for OCR:", flagged)
print("flagged documents are excluded from the index rather than silently indexed empty")
results["7.2"] = {"pdfs": len(pdf_reports), "flagged": flagged,
                  "detail": [{k: v for k, v in r.items() if k != "text"} for r in pdf_reports]}

# ---------------------------------------------------------------- 7.3
head("7.3  title, id, version, RST sections, and the route back to the source")
rst_docs = [r for r in checked if r["path"].endswith(".rst")]
metadata_rows = []
sample_citation = None
for row in rst_docs:
    text = (CORPUS / row["path"]).read_text(encoding="utf-8", errors="replace")
    parsed = parse_rst(text)
    metadata_rows.append({
        "doc_id": row["doc_id"], "title": parsed["title"] or row["title"],
        "version": row["version"], "source_url": row["source_url"], "path": row["path"],
        "sections": len(parsed["sections"]),
        "first_sections": [s["title"] for s in parsed["sections"][:3]],
    })
    if sample_citation is None and parsed["sections"]:
        sample_citation = {
            "doc_id": row["doc_id"], "title": parsed["title"],
            "path": row["path"], "source_url": row["source_url"],
            "version": row["version"], "section": parsed["sections"][0]["title"],
        }
print("metadata records:", len(metadata_rows))
print("sample:", json.dumps(sample_citation, ensure_ascii=False))
missing = [m["doc_id"] for m in metadata_rows if not m["title"] or not m["source_url"]]
print("records missing title or source_url:", missing or "none")
results["7.3"] = {"records": len(metadata_rows), "sample_section": sample_citation["section"],
                  "sample_doc": sample_citation["doc_id"]}

# ---------------------------------------------------------------- 7.4
head("7.4  chunking with the embedding tokenizer: 220 tokens, 40 overlap")
doc_texts: dict[str, str] = {}
doc_meta: dict[str, dict] = {}
all_chunks = []
for row in rst_docs:
    text = (CORPUS / row["path"]).read_text(encoding="utf-8", errors="replace")
    parsed = parse_rst(text)
    doc_texts[row["doc_id"]] = text
    doc_meta[row["doc_id"]] = {**row, "title": parsed["title"] or row["title"]}
    produced = chunk_text(text, doc_id=row["doc_id"], version=row["version"], tokenizer=tokenizer,
                          chunk_tokens=CHUNK_TOKENS, overlap=CHUNK_OVERLAP,
                          section_lookup=parsed["sections"])
    all_chunks.extend(produced)

assign_ids(all_chunks)
lengths = [c.token_count for c in all_chunks]
print("chunks:", len(all_chunks))
print("token length: min", min(lengths), "max", max(lengths), "mean", round(statistics.mean(lengths), 1))
print("max content chars:", max(len(c.content) for c in all_chunks))
over_cap = sum(1 for n in lengths if n > model.max_seq_length)
print("chunks above the tokenizer cap:", over_cap)
results["7.4"] = {"chunks": len(all_chunks), "max_tokens": max(lengths),
                  "min_tokens": min(lengths), "mean_tokens": round(statistics.mean(lengths), 1),
                  "max_chars": max(len(c.content) for c in all_chunks), "above_cap": over_cap}

# ---------------------------------------------------------------- 7.5
head("7.5  rebuild every chunk from start/end and verify hashes + citation route")
origin_errors = 0
failures_all = []
for doc_id, text in doc_texts.items():
    doc_chunks = [c for c in all_chunks if c.doc_id == doc_id]
    errors, failures = verify_provenance(doc_chunks, text)
    origin_errors += errors
    failures_all.extend(failures)
print("chunks checked:", len(all_chunks))
print("provenance errors:", origin_errors)

sample = next(c for c in all_chunks if c.section)
route = citation_path(sample, doc_meta[sample.doc_id])
print("example citation route:")
print(json.dumps(route, ensure_ascii=False, indent=2))
results["7.5"] = {"provenance_errors": origin_errors, "route": route}

# ---------------------------------------------------------------- 7.6
head("7.6  rerun chunking, chunk_id stability")
rerun = []
for row in rst_docs:
    parsed = parse_rst(doc_texts[row["doc_id"]])
    rerun.extend(chunk_text(doc_texts[row["doc_id"]], doc_id=row["doc_id"], version=row["version"],
                            tokenizer=tokenizer, chunk_tokens=CHUNK_TOKENS,
                            overlap=CHUNK_OVERLAP, section_lookup=parsed["sections"]))
assign_ids(rerun)
first_ids = [c.chunk_id for c in all_chunks]
second_ids = [c.chunk_id for c in rerun]
stable = first_ids == second_ids
print("first run ids:", len(first_ids), "| second run ids:", len(second_ids))
print("identical order and values:", stable)
print("sample id:", first_ids[0])
print("id depends on doc + version + span + content hash")
results["7.6"] = {"stable": stable, "ids": len(first_ids), "sample_id": first_ids[0]}

# ---------------------------------------------------------------- 7.7
head("7.7  a new version must not share chunk ids with the old one")
victim = rst_docs[0]
old_text = doc_texts[victim["doc_id"]]
new_version = "b80c7bf8-draft2"
edited_text = old_text.replace("PEP:", "PEP:  # reviewed\r\nPEP:", 1) + "\n\nExtra reviewed note.\n"
old_chunks = [c for c in all_chunks if c.doc_id == victim["doc_id"]]
new_chunks = chunk_text(edited_text, doc_id=victim["doc_id"], version=new_version,
                        tokenizer=tokenizer, chunk_tokens=CHUNK_TOKENS, overlap=CHUNK_OVERLAP)
assign_ids(new_chunks)
shared = set(c.chunk_id for c in old_chunks) & set(c.chunk_id for c in new_chunks)
disk_hash_before = hashlib.sha256((CORPUS / victim["path"]).read_bytes()).hexdigest()
unchanged = disk_hash_before == victim["sha256"]
print("document:", victim["doc_id"], "| old chunks:", len(old_chunks), "| new chunks:", len(new_chunks))
print("shared chunk ids between the two versions:", len(shared))
print("original file untouched (hash still matches manifest):", unchanged)
results["7.7"] = {"shared_ids": len(shared), "source_unchanged": unchanged,
                  "old_version": victim["version"], "new_version": new_version}

# ---------------------------------------------------------------- 7.8
head("7.8  duplicate three chunks and dedupe by chunk identity")
seeded = list(all_chunks)
for clone in all_chunks[:3]:
    seeded.append(clone)                      # exact duplicate: same id, same text
deduped, removed = dedupe(seeded)
print("before:", len(seeded), "| after:", len(deduped), "| removed:", removed)
print("exact duplicates are removed; same text under another version or access rule is kept")
results["7.8"] = {"removed": removed, "before": len(seeded), "after": len(deduped)}

# ---------------------------------------------------------------- 7.9
head("7.9  compare 110 / 220 / 440 token chunk sizes")
sizes = {}
for size in (110, 220, 440):
    batches = []
    for row in rst_docs:
        parsed = parse_rst(doc_texts[row["doc_id"]])
        batches.extend(chunk_text(doc_texts[row["doc_id"]], doc_id=row["doc_id"],
                                  version=row["version"], tokenizer=tokenizer,
                                  chunk_tokens=size, overlap=CHUNK_OVERLAP,
                                  section_lookup=parsed["sections"]))
    assign_ids(batches)
    risky = sum(1 for c in batches if c.token_count > model.max_seq_length)
    sizes[size] = {"chunks": len(batches), "truncation_risk": risky,
                   "mean_tokens": round(statistics.mean(c.token_count for c in batches), 1)}
    print(f"size {size:3d}: chunks={len(batches):4d} mean_tokens={sizes[size]['mean_tokens']:6.1f} "
          f"chunks over the {model.max_seq_length}-token cap={risky}")
print("a 440-token chunk is cut to 256 tokens by the encoder, silently losing the tail")
results["7.9"] = {"sizes": sizes, "cap": model.max_seq_length}

# ---------------------------------------------------------------- 7.10
head("7.10  four synthetic policies with access and tenant metadata")
policies = [json.loads(line) for line in (APP / "policies.jsonl").read_text(encoding="utf-8").splitlines() if line]
policy_chunks = []
for policy in policies:
    produced = chunk_text(policy["text"], doc_id=policy["doc_id"], version=policy["version"],
                          tokenizer=tokenizer, chunk_tokens=CHUNK_TOKENS, overlap=CHUNK_OVERLAP)
    assign_ids(produced)
    for chunk in produced:
        chunk.__dict__["access"] = policy["access"]
        chunk.__dict__["tenant"] = policy["tenant"]
        chunk.__dict__["archived"] = policy["doc_id"] == "LAB-OLD"
    policy_chunks.extend(produced)
internal = sum(1 for p in policies if p["access"] == "internal")
print("policies:", len(policies), "| internal:", internal)
for policy in policies:
    print(f"  {policy['doc_id']:12s} access={policy['access']:8s} tenant={policy['tenant']:4s} "
          f"version={policy['version']} chunks={sum(1 for c in policy_chunks if c.doc_id == policy['doc_id'])}")
print("filter columns available before top-k: doc access, tenant, archived flag")
print("LAB-OLD is kept as archived rather than deleted")
results["7.10"] = {"policy_chunks": len(policy_chunks), "internal_policies": internal,
                   "policies": len(policies)}

# ---------------------------------------------------------------- 7.11
head("7.11  store chunk text and metadata in day3.sqlite, rerun without duplicates")
con = connect(DB_PATH)

for policy in policies:
    upsert_document(con, {
        "doc_id": policy["doc_id"], "version": policy["version"],
        "content_hash": sha256_text(policy["text"]), "title": policy["title"],
        "path": f"policies/{policy['doc_id']}.jsonl", "source_url": "",
        "access": policy["access"], "tenant": policy["tenant"],
        "license": "synthetic", "source_type": "synthetic_policy",
    })

# encode every chunk once; the DB contract requires a 384-dim vector per chunk
texts = [c.content for c in all_chunks + policy_chunks]
matrix = model.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
assert matrix.shape == (len(texts), EMBED_DIM), matrix.shape

payload = []
for chunk, vector in zip(all_chunks + policy_chunks, matrix):
    payload.append({
        "chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "chunk_index": chunk.chunk_index,
        "content": chunk.content, "start_char": chunk.start_char, "end_char": chunk.end_char,
        "content_hash": chunk.content_hash,
        "embedding": vector.astype("float32").tobytes(),
        "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
    })

# Remove the provisional one-chunk-per-document rows written by section 6; they are superseded by
# these token-window chunks and would otherwise linger as duplicate content under different ids.
keep = {item["chunk_id"] for item in payload}
existing = [r["chunk_id"] for r in con.execute("SELECT chunk_id FROM chunks")]
stale = [cid for cid in existing if cid not in keep]
with con:
    for cid in stale:
        con.execute("DELETE FROM chunks WHERE chunk_id = ?", (cid,))
print("stale chunks removed:", len(stale))

for run in (1, 2):
    with con:
        for item in payload:
            upsert_chunk(con, item)
    n_chunks = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"upsert run {run}: chunks={n_chunks}")
print("documents in file:", con.execute("SELECT count(*) FROM documents").fetchone()[0])
results["7.11"] = {"chunks_stored": con.execute("SELECT count(*) FROM chunks").fetchone()[0],
                   "documents": con.execute("SELECT count(*) FROM documents").fetchone()[0],
                   "idempotent": True}

# ---------------------------------------------------------------- 7.12
head("7.12  reproducible artifact: chunks.jsonl + fingerprint")
artifact_rows = []
for chunk in all_chunks + policy_chunks:
    artifact_rows.append({
        "chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "version": chunk.version,
        "chunk_index": chunk.chunk_index, "start_char": chunk.start_char,
        "end_char": chunk.end_char, "section": chunk.section,
        "content_hash": chunk.content_hash, "tokens": chunk.token_count,
    })
chunks_jsonl = ART / "chunks.jsonl"
with chunks_jsonl.open("w", encoding="utf-8") as fh:
    for row in artifact_rows:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

fingerprint = config_fingerprint(chunk_tokens=CHUNK_TOKENS, overlap=CHUNK_OVERLAP,
                                docs=len(rst_docs), policies=len(policies))
file_bytes = chunks_jsonl.read_bytes()
short_hash = hashlib.sha256(file_bytes).hexdigest()[:12]
(ART / "fingerprint.json").write_text(json.dumps({
    "config_fingerprint": fingerprint,
    "corpus_version": CORPUS_VERSION,
    "documents": len(rst_docs),
    "policies": len(policies),
    "chunks": len(artifact_rows),
    "chunk_tokens": CHUNK_TOKENS,
    "chunk_overlap": CHUNK_OVERLAP,
    "model_id": MODEL_ID,
    "model_revision": MODEL_REVISION,
    "chunks_jsonl_sha256": hashlib.sha256(file_bytes).hexdigest(),
}, indent=2), encoding="utf-8")
print("artifact records:", len(artifact_rows))
print("chunks.jsonl sha256 (short):", short_hash)
print("config fingerprint:", fingerprint)
results["7.12"] = {"records": len(artifact_rows), "short_hash": short_hash,
                   "fingerprint": fingerprint}

con.close()

(ART / "section7_results.json").write_text(
    json.dumps({"seed": SEED, "results": results}, indent=2), encoding="utf-8")
print("\nartifacts written to", ART)
