"""Single source of truth for seed, model identity, and chunk settings."""
from __future__ import annotations

import hashlib
import json

SEED = 20261015

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EMBED_DIM = 384
MODEL_MAX_TOKENS = 256

CHUNK_TOKENS = 220
CHUNK_OVERLAP = 40

CORPUS_VERSION = "b80c7bf8d5a89fc47b732504a9e1219b79677531"


def config_fingerprint(**overrides) -> str:
    """Stable hash of the settings that shape an artifact."""
    payload = {
        "seed": SEED,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "chunk_tokens": CHUNK_TOKENS,
        "chunk_overlap": CHUNK_OVERLAP,
        "corpus_version": CORPUS_VERSION,
    }
    payload.update(overrides)
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
