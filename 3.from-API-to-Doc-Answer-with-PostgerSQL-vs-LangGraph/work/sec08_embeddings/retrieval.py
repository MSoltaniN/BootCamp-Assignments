"""Retrieval building blocks: index loading, dense cosine, lexical TF-IDF, RRF, ACL, context.

Design notes that the sub-questions depend on:

* Rankings are computed on chunks but reported per **document** (max score per doc, distinct docs).
  Section 9 defines relevance at document level, so aggregating any other way would be wrong.
* Lexical and dense scores live on different scales. They are never added; only ranks are fused.
* ACL filtering happens *before* top-k, so a forbidden document never influences the ranking.
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

DIM = 384
RRF_K = 60


# ----------------------------------------------------------------------------- index
@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    content: str
    embedding: np.ndarray
    model_id: str
    model_revision: str
    access: str | None = None
    tenant: str | None = None
    archived: bool = False


@dataclass
class Index:
    chunks: list[ChunkRecord]
    matrix: np.ndarray
    metadata: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.chunks)

    @property
    def doc_ids(self) -> list[str]:
        return sorted({c.doc_id for c in self.chunks})


class IndexIncompatible(RuntimeError):
    """Raised when the stored index cannot be trusted for the configured model or chunking."""


def decode_blob(raw: bytes | None) -> np.ndarray | None:
    if raw is None:
        return None
    raw = bytes(raw)
    if len(raw) != DIM * 4:
        return None
    return np.array(struct.unpack(f"<{DIM}f", raw), dtype=np.float32)


def load_index(con, *, expect: dict | None = None) -> Index:
    """Read chunks and their vectors, and refuse to serve an index that does not match `expect`.

    Validation happens once, before any query. A mismatched model revision or dimension makes
    every similarity meaningless, so it is an error rather than a warning.
    """
    rows = con.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.content, c.embedding, c.model_id, c.model_revision,
               d.access, d.tenant
        FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
        ORDER BY c.chunk_id
        """
    ).fetchall()

    chunks: list[ChunkRecord] = []
    vectors: list[np.ndarray] = []
    bad_vectors = 0
    for row in rows:
        vector = decode_blob(row["embedding"])
        if vector is None:
            bad_vectors += 1
            continue
        chunks.append(ChunkRecord(
            chunk_id=row["chunk_id"], doc_id=row["doc_id"], content=row["content"],
            embedding=vector, model_id=row["model_id"], model_revision=row["model_revision"],
            access=row["access"], tenant=row["tenant"],
            archived=row["doc_id"].endswith("OLD"),
        ))
        vectors.append(vector)

    if not chunks:
        raise IndexIncompatible("the index contains no usable 384-dim vectors")

    matrix = np.vstack(vectors)
    metadata = {
        "chunks": len(chunks),
        "documents": len({c.doc_id for c in chunks}),
        "dimension": int(matrix.shape[1]),
        "model_ids": sorted({c.model_id for c in chunks}),
        "model_revisions": sorted({c.model_revision for c in chunks}),
        "unreadable_vectors": bad_vectors,
    }

    if expect:
        problems = []
        if expect.get("dimension") and expect["dimension"] != metadata["dimension"]:
            problems.append(f"dimension {metadata['dimension']} != expected {expect['dimension']}")
        if expect.get("model_revision") and expect["model_revision"] not in metadata["model_revisions"]:
            problems.append(f"model revision {metadata['model_revisions']} != expected {expect['model_revision']}")
        if expect.get("model_id") and expect["model_id"] not in metadata["model_ids"]:
            problems.append(f"model id {metadata['model_ids']} != expected {expect['model_id']}")
        if expect.get("min_chunks") and metadata["chunks"] < expect["min_chunks"]:
            problems.append(f"only {metadata['chunks']} chunks indexed")
        if problems:
            raise IndexIncompatible("; ".join(problems))

    return Index(chunks=chunks, matrix=matrix, metadata=metadata)


# ----------------------------------------------------------------------------- similarity
def cosine_explicit(a: np.ndarray, b: np.ndarray) -> float:
    """Explicit formula: dot(a, b) / (||a|| * ||b||)."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def cosine_via_dot(a: np.ndarray, b: np.ndarray) -> float:
    """Equivalent form once both vectors are L2-normalised: the norms are 1, so it is just dot."""
    na = a / np.linalg.norm(a)
    nb = b / np.linalg.norm(b)
    return float(np.dot(na, nb))


def cosine_distance(similarity: float) -> float:
    """cosine distance = 1 - similarity; smaller is closer, the opposite direction of similarity."""
    return 1.0 - similarity


def dense_scores(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """One matrix product for all chunks. Vectors are normalised, so dot == cosine."""
    q = query_vector / (np.linalg.norm(query_vector) or 1.0)
    return matrix @ q


# ----------------------------------------------------------------------------- document aggregation
@dataclass
class DocHit:
    doc_id: str
    score: float
    chunk_ids: list[str]
    best_chunk: str


def aggregate_to_documents(chunks: Iterable[ChunkRecord], scores: np.ndarray,
                           order: str = "desc") -> list[DocHit]:
    """Collapse chunk scores into a distinct-document ranking.

    Several chunks of one document must not occupy several ranks: relevance is document level,
    so only the best-scoring chunk of each document carries the document's score.
    """
    best: dict[str, DocHit] = {}
    for chunk, score in zip(chunks, scores):
        hit = best.get(chunk.doc_id)
        if hit is None:
            best[chunk.doc_id] = DocHit(chunk.doc_id, float(score), [chunk.chunk_id], chunk.chunk_id)
            continue
        hit.chunk_ids.append(chunk.chunk_id)
        if (order == "desc" and score > hit.score) or (order == "asc" and score < hit.score):
            hit.score = float(score)
            hit.best_chunk = chunk.chunk_id
    return sorted(best.values(), key=lambda h: h.score, reverse=(order == "desc"))


# ----------------------------------------------------------------------------- lexical
def build_tfidf(texts: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True)
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def lexical_scores(vectorizer, matrix, query: str) -> np.ndarray:
    q = vectorizer.transform([query])
    return np.asarray((matrix @ q.T).toarray()).ravel()


# ----------------------------------------------------------------------------- fusion
def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Fuse ranked id lists by rank only.

    Score magnitudes are discarded deliberately: TF-IDF scores and cosine similarities are not
    comparable, so adding them would let whichever scale happens to be larger dominate.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


# ----------------------------------------------------------------------------- ACL
@dataclass
class Principal:
    user_id: str
    role: str
    tenant: str


def visible(chunk: ChunkRecord, principal: Principal, *, include_archived: bool = True) -> bool:
    """Authorization evaluated per chunk, before ranking.

    Admin sees every tenant but archived material is still marked, and a student only sees public
    documents plus their own tenant's internal ones.
    """
    if chunk.archived and not include_archived:
        return False
    if principal.role == "admin":
        return True
    if (chunk.access or "public") == "public":
        return True
    return (chunk.tenant or "all") in ("all", principal.tenant)


def acl_filter(chunks: list[ChunkRecord], principal: Principal, *,
               include_archived: bool = True) -> list[ChunkRecord]:
    return [c for c in chunks if visible(c, principal, include_archived=include_archived)]


# ----------------------------------------------------------------------------- context
@dataclass
class Context:
    text: str
    tokens: int
    selected: list[str]
    dropped: list[str]
    truncated_last: bool = False


def build_context(hits: list[DocHit], chunk_lookup: dict[str, ChunkRecord], tokenizer,
                  *, max_tokens: int = 700, header_tokens: int = 8) -> Context:
    """Pack evidence in rank order until the budget is exhausted, then stop.

    Dropped evidence is reported rather than silently omitted, because the prompt cost and the
    coverage both depend on how much was left out.
    """
    selected: list[str] = []
    dropped: list[str] = []
    pieces: list[str] = []
    used = header_tokens
    truncated = False

    for hit in hits:
        chunk = chunk_lookup.get(hit.best_chunk)
        if chunk is None:
            dropped.append(hit.best_chunk)
            continue
        piece = f"[{chunk.chunk_id}] {chunk.content.strip()}"
        ids = tokenizer.encode(piece, add_special_tokens=False)

        if used + len(ids) <= max_tokens:
            pieces.append(piece)
            selected.append(chunk.chunk_id)
            used += len(ids)
            continue

        remaining = max_tokens - used
        if remaining > 20:
            # Partially kept: it is selected (its text is present) and also reported as
            # truncated, but it is not counted twice in the selected/dropped tallies.
            kept = ids[:remaining]
            pieces.append(tokenizer.decode(kept))
            selected.append(chunk.chunk_id)
            used += len(kept)
            truncated = True
        else:
            dropped.append(chunk.chunk_id)

    text = "\n\n".join(pieces)
    actual = len(tokenizer.encode(text, add_special_tokens=False))
    return Context(text=text, tokens=actual, selected=selected,
                   dropped=dropped, truncated_last=truncated)


# ----------------------------------------------------------------------------- fingerprint
def index_fingerprint(index: Index, config: dict) -> dict:
    import hashlib

    digest = hashlib.sha256()
    for chunk in index.chunks:
        digest.update(chunk.chunk_id.encode("utf-8"))
        digest.update(chunk.content.encode("utf-8"))
    return {
        "chunks": len(index.chunks),
        "documents": index.metadata["documents"],
        "dimension": index.metadata["dimension"],
        "model_id": index.metadata["model_ids"],
        "model_revision": index.metadata["model_revisions"],
        "chunk_config": {"tokens": config.get("chunk_tokens"), "overlap": config.get("chunk_overlap")},
        "content_digest": digest.hexdigest()[:16],
    }


def save_fingerprint(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------- latency
def percentiles(samples_ms: list[float]) -> dict:
    if not samples_ms:
        return {"p50": None, "p95": None, "n": 0}
    ordered = sorted(samples_ms)
    def pick(p: float) -> float:
        position = (len(ordered) - 1) * p
        low, high = math.floor(position), math.ceil(position)
        if low == high:
            return round(ordered[int(position)], 3)
        return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)
    return {"p50": pick(0.50), "p95": pick(0.95), "n": len(ordered)}
