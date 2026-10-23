"""Verify the working environment for assignment 3.

Checks Python, SQLite, the pinned libraries, the embedding model files against
`resources/embedding_model_manifest.json`, and optionally runs one encode call
to prove the model actually loads offline.

    python scripts/check_env.py            # libraries + model files
    python scripts/check_env.py --encode   # also encode a probe sentence

Writes `artifacts/env_report.json` and exits non-zero if anything required is
missing.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "resources" / "embedding_model_manifest.json"
MODEL_DIR = ROOT / "resources" / "embedding_model"
OUT = ROOT / "artifacts" / "env_report.json"

REQUIRED = [
    "numpy", "pandas", "scipy", "sklearn", "torch", "matplotlib",
    "sentence_transformers", "transformers", "fastapi", "httpx", "uvicorn",
    "langgraph", "pydantic", "jwt", "pypdf", "nbformat", "nbclient",
]
OPTIONAL = ["jupyterlab", "huggingface_hub"]

# module name -> candidate distribution names for importlib.metadata
DIST_NAMES = {
    "sklearn": ["scikit-learn"],
    "sentence_transformers": ["sentence-transformers"],
    "jwt": ["PyJWT"],
    "huggingface_hub": ["huggingface-hub"],
}


def version_of(module: str) -> str:
    """Version from installed metadata first (works for langgraph, which has no __version__)."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover
        version = None  # type: ignore[assignment]
    if version is not None:
        for dist in DIST_NAMES.get(module, [module.replace("_", "-")]):
            try:
                return version(dist)
            except Exception:  # noqa: BLE001 - try the next candidate name
                continue
    try:
        mod = __import__(module)
    except Exception as exc:  # noqa: BLE001 - reporting, not handling
        return f"MISSING ({type(exc).__name__})"
    for attr in ("__version__", "version"):
        v = getattr(mod, attr, None)
        if isinstance(v, str):
            return v
    return "installed"


def model_files() -> dict:
    if not MANIFEST.exists():
        return {"status": "manifest missing"}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems, checked = [], 0
    for item in manifest["files"]:
        p = MODEL_DIR / item["path"]
        if not p.exists():
            problems.append(f"{item['path']}: missing")
            continue
        checked += 1
        if hashlib.sha256(p.read_bytes()).hexdigest() != item["sha256"]:
            problems.append(f"{item['path']}: sha256 mismatch")
    return {
        "status": "ok" if not problems and checked == len(manifest["files"]) else "incomplete",
        "model_id": manifest["model_id"],
        "revision": manifest["revision"],
        "dimensions": manifest["dimensions"],
        "max_sequence_length": manifest["max_sequence_length"],
        "license": manifest["license"],
        "files_checked": checked,
        "files_expected": len(manifest["files"]),
        "problems": problems,
        "dir": str(MODEL_DIR),
    }


def encode_probe() -> dict:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # noqa: BLE001
        return {"status": f"sentence_transformers unavailable: {type(exc).__name__}"}
    if not MODEL_DIR.exists():
        return {"status": "model dir missing"}
    t0 = time.perf_counter()
    model = SentenceTransformer(str(MODEL_DIR), device="cpu", local_files_only=True)
    load_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    vec = model.encode(["Use 4 spaces per indentation level."], normalize_embeddings=True)[0]
    encode_ms = (time.perf_counter() - t1) * 1000
    return {
        "status": "ok",
        "load_seconds": round(load_s, 3),
        "encode_ms": round(encode_ms, 1),
        "dimensions": int(vec.shape[0]),
        "l2_norm": round(float((vec ** 2).sum() ** 0.5), 6),
        "max_seq_length": model.max_seq_length,
        "tokenizer_max": model.tokenizer.model_max_length,
    }


def main() -> int:
    do_encode = "--encode" in sys.argv[1:]
    report = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "executable": sys.executable,
        "in_venv": sys.prefix != sys.base_prefix,
        "sqlite_version": sqlite3.sqlite_version,
        "packages": {m: version_of(m) for m in REQUIRED},
        "optional": {m: version_of(m) for m in OPTIONAL},
        "model": model_files(),
    }
    if do_encode:
        report["model"]["encode_probe"] = encode_probe()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"python {report['python']}  venv={report['in_venv']}  sqlite {report['sqlite_version']}")
    print("-" * 52)
    missing = []
    for name, ver in report["packages"].items():
        flag = "OK   " if not ver.startswith("MISSING") else "MISS"
        if ver.startswith("MISSING"):
            missing.append(name)
        print(f"{flag} {name:24} {ver}")
    print("-" * 52)
    print("model:", report["model"]["status"], f"({report['model'].get('files_checked', 0)}"
          f"/{report['model'].get('files_expected', 0)} files)")
    if "encode_probe" in report["model"]:
        print("encode probe:", report["model"]["encode_probe"])
    print("written:", OUT)
    if missing:
        print("missing packages:", ", ".join(missing))
    return 1 if missing or report["model"]["status"] != "ok" else 0


if __name__ == "__main__":
    sys.exit(main())
