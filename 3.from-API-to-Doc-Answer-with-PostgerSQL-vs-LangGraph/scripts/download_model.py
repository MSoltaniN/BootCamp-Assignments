"""One-time offline download of the pinned embedding model.

The assignment fixes `sentence-transformers/all-MiniLM-L6-v2` at revision
1110a243... and hashes every file in `resources/embedding_model_manifest.json`.
After this runs once, nothing in the assignment needs the network again.

    python scripts/download_model.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "resources" / "embedding_model_manifest.json"
TARGET = ROOT / "resources" / "embedding_model"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if TARGET.exists() and any(TARGET.iterdir()):
        print(f"already present: {TARGET}")
    else:
        from huggingface_hub import snapshot_download

        print(f"downloading {manifest['model_id']} @ {manifest['revision'][:12]} ...")
        snapshot_download(
            manifest["model_id"],
            revision=manifest["revision"],
            local_dir=str(TARGET),
        )
        print("downloaded")

    bad = []
    for item in manifest["files"]:
        p = TARGET / item["path"]
        if not p.exists():
            bad.append((item["path"], "missing"))
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h != item["sha256"]:
            bad.append((item["path"], "sha256 mismatch"))
    print(f"files checked: {len(manifest['files'])}, problems: {len(bad)}")
    for path, why in bad:
        print(f"  FAIL {path}: {why}")
    print("model dir:", TARGET)
    print("dims:", manifest["dimensions"], "max tokens:", manifest["max_sequence_length"],
          "license:", manifest["license"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
