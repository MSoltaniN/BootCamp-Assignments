"""Run a Python script with the sandbox ``mkdtemp`` shim applied.

    python scripts/sandbox_run.py scripts/download_model.py
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox_compat import patch_mkdtemp  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/sandbox_run.py <script.py> [args...]")
        raise SystemExit(2)
    target = sys.argv[1]
    sys.argv = sys.argv[1:]
    patch_mkdtemp()
    runpy.run_path(target, run_name="__main__")
