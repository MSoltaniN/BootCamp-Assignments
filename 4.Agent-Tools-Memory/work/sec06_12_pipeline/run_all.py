"""Single entry point for sections 6-12.

The per-section folders hold the answers; this runner owns the execution order,
because the sections genuinely depend on each other:

    6 tools/MCP  ->  7 loop uses those tools  ->  8 persists loop output
      ->  9 router (needs profiles from 5)  ->  10 attacks all of the above
      ->  11 scores the logs  ->  12 gates and ships

Splitting the runner per section would mean re-running 6 seven times, so the
orchestration stays here while each section's answers live in its own folder.

Run:
    .venv\\Scripts\\python.exe work/sec06_12_pipeline/run_all.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "work" / "sec06_12_pipeline" / "run_sections_6_to_12.py"


def main() -> int:
    if not RUNNER.exists():
        print(f"runner missing: {RUNNER}")
        return 1

    print("delegating to", RUNNER.name)
    result = subprocess.run([sys.executable, str(RUNNER)], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
