"""Shared helpers for the Day5 practical sections.

Design rules:
  * never import `pickle`; all npz loads use `allow_pickle=False`
  * every path resolves from the repo root so scripts can run from anywhere
  * JSON is written with `ensure_ascii=False` so Persian stays readable
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assignment" / "source" / "Day5"
DATA = SRC / "Day5_Datasets"
RESOURCES = SRC / "Day5_Resources"
MODELS = RESOURCES / "models"
OUT = ROOT / "Day5_Run_Output"
SECTIONS = ROOT / "sections"

# ---- pinned facts from the bundle (single source of truth) -------------------
MODEL_REVISION = "9217f5db79a29953eb74d5343926648285ec7e67"
ENGINE_RELEASE = "b11696"

MODEL_HASHES = {
    "qwen2.5-0.5b-instruct-q4_k_m.gguf": "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
    "qwen2.5-0.5b-instruct-q8_0.gguf": "ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e",
}

GIB = 2 ** 30
GB = 10 ** 9


# ---- io ---------------------------------------------------------------------
def out_dir(section: str | None = None) -> Path:
    """Return the flat artifact root; sections write here directly."""
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT


def section_out(slug: str) -> Path:
    """Per-section scratch folder (charts, logs). Final artifacts go to OUT."""
    d = SECTIONS / slug / "out"
    d.mkdir(parents=True, exist_ok=True)
    return d


def section_src(slug: str) -> Path:
    d = SECTIONS / slug / "src"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(path: Path, obj: Any, *, indent: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def sha256_file(path: Path, chunk: int = 2 ** 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


# ---- numerics ---------------------------------------------------------------
def gib(n_bytes: float) -> float:
    return n_bytes / GIB


def weight_bytes(total_b: float, bits: int) -> float:
    """Raw weight size in bytes for `total_b` billion parameters at `bits` bits.

    Always uses TOTAL parameters, never the active count: every expert must be
    resident even when only a few are active per token.
    """
    return total_b * 1e9 * bits / 8


def kv_bytes(*, layers: int, kv_heads: int, head_dim: int, tokens: int,
             concurrency: int = 1, dtype_bytes: int = 2) -> float:
    """KV cache size in bytes: 2 (K and V) x layers x kv_heads x head_dim x dtype x tokens x concurrency."""
    return 2 * layers * kv_heads * head_dim * dtype_bytes * tokens * concurrency


def quantile(values: list[float], q: float) -> float:
    """Linear-interpolation quantile matching numpy's default (`linear`)."""
    if not values:
        raise ValueError("empty")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def ecdf(values: list[float]) -> tuple[list[float], list[float]]:
    xs = sorted(values)
    n = len(xs)
    ys = [(i + 1) / n for i in range(n)]
    return xs, ys


# ---- llm server -------------------------------------------------------------
def engine_path() -> Path:
    """Locate llama-server without assuming the OS-specific folder name."""
    override = os.environ.get("LLAMA_SERVER_PATH")
    if override:
        p = Path(override)
        if p.exists():
            return p
        raise FileNotFoundError(f"LLAMA_SERVER_PATH points nowhere: {p}")
    for candidate in (
        RESOURCES / "llama_cpp" / "llama-server.exe",
        RESOURCES / "llama_cpp" / "llama-server",
        RESOURCES / "llama_cpp" / "build" / "bin" / "llama-server.exe",
        RESOURCES / "llama_cpp" / "build" / "bin" / "llama-server",
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "llama-server not found. Run Day5_Starter/download_resources.py or set LLAMA_SERVER_PATH."
    )


def model_path(quant: str) -> Path:
    name = f"qwen2.5-0.5b-instruct-{quant}.gguf"
    p = MODELS / name
    if not p.exists():
        raise FileNotFoundError(f"model missing: {p} (run download_resources.py)")
    return p
