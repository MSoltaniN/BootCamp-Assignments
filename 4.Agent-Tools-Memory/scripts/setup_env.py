"""Install the Day 4 dependencies with logging and graceful fallback.

The pack pins very new versions (numpy 2.4.2, pandas 3.0.0, ...). If an exact
pin is unavailable on the current Python, the script falls back to the newest
compatible release for that package instead of failing the whole run.

Run with the venv interpreter:

    .venv\\Scripts\\python.exe scripts\\setup_env.py

Everything is logged to docs/generated/qa/_setup_env.log.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "assignment" / "source" / "Day4" / "requirements-day4.txt"
LOG = ROOT / "docs" / "generated" / "qa" / "_setup_env.log"

# import name -> pip requirement name
REQUIRED_IMPORTS = {
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "sklearn": "scikit-learn",
    "pydantic": "pydantic",
    "mcp": "mcp",
    "langgraph": "langgraph",
    "langgraph.checkpoint.sqlite": "langgraph-checkpoint-sqlite",
    "nbformat": "nbformat",
    "nbclient": "nbclient",
    "ipykernel": "ipykernel",
}


# `--no-cache-dir` matters: concurrent pip runs deadlock on pip's shared HTTP
# cache lock on Windows, and stale lock holders make every later install hang
# silently. Bypassing the cache sidesteps it entirely.
PIP_FLAGS = [
    "--no-cache-dir",
    "--disable-pip-version-check",
    "--progress-bar", "off",
    "--timeout", "30",
    "--retries", "2",
]


def run(args: list[str], *, quiet: bool = False) -> tuple[int, str]:
    result = subprocess.run(
        [str(VENV_PY), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    if not quiet:
        print(output[-1500:])
    return result.returncode, output


def installed_version(module: str) -> str | None:
    code = (
        "import importlib.metadata as m, sys\n"
        f"name = {REQUIRED_IMPORTS[module]!r}\n"
        "try:\n"
        "    print(m.version(name))\n"
        "except m.PackageNotFoundError:\n"
        "    sys.exit(1)\n"
    )
    status, out = run(["-c", code], quiet=True)
    return out.strip() if status == 0 else None


def present(module: str) -> bool:
    status, _ = run(["-c", f"import {module}"], quiet=True)
    return status == 0


def parse_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            pins[name.strip()] = version.strip()
    return pins


def main() -> int:
    if not VENV_PY.exists():
        print(f"venv interpreter missing: {VENV_PY}")
        print("Create it first: python -m venv .venv")
        return 1

    LOG.parent.mkdir(parents=True, exist_ok=True)
    log: list[str] = []

    def note(message: str) -> None:
        print(message)
        log.append(message)

    status, out = run(["--version"], quiet=True)
    note(f"interpreter: {out.strip()}")

    pins = parse_pins()
    note(f"requirements: {len(pins)} pinned packages")

    failures: list[str] = []
    for module, requirement in REQUIRED_IMPORTS.items():
        if present(module):
            note(f"  [have] {requirement} {installed_version(module)}")
            continue

        pinned = pins.get(requirement)
        if pinned:
            note(f"  [try ] {requirement}=={pinned}")
            code, output = run(["-m", "pip", "install", "--quiet",
                                *PIP_FLAGS, f"{requirement}=={pinned}"])
            if code == 0 and present(module):
                note(f"  [ok  ] {requirement}=={pinned}")
                continue
            note(f"  [miss] {requirement}=={pinned} unavailable, trying latest")
            log.append(output[-800:])

        note(f"  [try ] {requirement} (latest)")
        code, output = run(["-m", "pip", "install", "--quiet",
                            *PIP_FLAGS, requirement])
        if code == 0 and present(module):
            note(f"  [ok  ] {requirement} {installed_version(module)}")
        else:
            note(f"  [FAIL] {requirement}")
            log.append(output[-800:])
            failures.append(requirement)

    note("")
    note("== FINAL ==")
    for module, requirement in REQUIRED_IMPORTS.items():
        state = installed_version(module) or "MISSING"
        note(f"  {requirement:<32} {state}")

    LOG.write_text("\n".join(log), encoding="utf-8")
    note(f"\nlog: {LOG}")

    if failures:
        note(f"FAILED: {failures}")
        return 1

    note("ENVIRONMENT READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
