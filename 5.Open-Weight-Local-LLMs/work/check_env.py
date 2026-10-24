"""Report the Day5 environment state without modifying anything.

Run with the project venv:
    set PYTHONIOENCODING=utf-8 && chcp 65001 >nul
    .venv5\\Scripts\\python.exe work\\check_env.py
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assignment" / "source" / "Day5"
RES = SRC / "Day5_Resources"
DATA = SRC / "Day5_Datasets"
OUT = ROOT / "Day5_Run_Output"

REQUIRED_MODELS = {
    "qwen2.5-0.5b-instruct-q4_k_m.gguf": (491400032, "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"),
    "qwen2.5-0.5b-instruct-q8_0.gguf": (675710816, "ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e"),
}

# torch is intentionally absent: section 11 trains a 16x8 linear layer with numpy.
PACKAGES = ["numpy", "pandas", "matplotlib", "requests", "nbformat", "nbclient", "ipykernel"]

VERDICT_ARTIFACTS = [
    "selection.json", "runtime_config.json", "test_predictions.jsonl", "selected_adapter.npz",
    "adapter_selection.json", "adapter_test_predictions.npy", "quantization_selection.json",
    "quant_test_predictions.npy", "local_agent.sqlite", "agent_trace.json", "security_tests.json",
]


def line(label: str, value: str) -> None:
    print(f"  {label:<26} {value}")


def main() -> int:
    ok = True
    print("== Runtime ==")
    line("python", sys.version.split()[0])
    line("executable", sys.executable)
    line("platform", platform.platform())
    line("in venv", str(sys.prefix != sys.base_prefix))
    line("prefix", sys.prefix)

    print("\n== Packages ==")
    for name in PACKAGES:
        try:
            mod = __import__(name)
            line(name, getattr(mod, "__version__", "?"))
        except ImportError:
            line(name, "MISSING")
            ok = False
    print("  torch                       not required (numpy-only adapter)")

    print("\n== Bundle ==")
    for label, path in [
        ("assignment source", SRC),
        ("datasets", DATA),
        ("resources", RES),
        ("Student_Template", SRC / "Day5_Starter" / "Student_Template.ipynb"),
        ("checker", SRC / "Day5_Grading" / "check_submission.py"),
        ("resource manifest", RES / "resource_manifest.json"),
    ]:
        exists = path.exists()
        line(label, "ok" if exists else "MISSING")
        ok = ok and exists

    print("\n== Models ==")
    for name, (size, _sha) in REQUIRED_MODELS.items():
        p = RES / "models" / name
        if not p.exists():
            line(name, "MISSING")
            ok = False
            continue
        actual = p.stat().st_size
        good = actual == size
        line(name, f"{actual:,} bytes {'ok' if good else f'SIZE MISMATCH expect {size}'}")
        ok = ok and good

    print("\n== Engine ==")
    server = RES / "llama_cpp" / "llama-server.exe"
    line("llama-server.exe", "ok" if server.exists() else "MISSING")
    ok = ok and server.exists()

    print("\n== Artifacts ==")
    present = []
    missing = []
    for name in VERDICT_ARTIFACTS:
        (present if (OUT / name).exists() else missing).append(name)
    line("required present", f"{len(present)}/{len(VERDICT_ARTIFACTS)}")
    if missing:
        line("still missing", ", ".join(missing))
    line("other outputs", ", ".join(sorted(p.name for p in OUT.glob("*") if p.name not in VERDICT_ARTIFACTS)) or "-")

    print("\n== Verdict ==")
    print("ENV READY" if ok else "ENV NOT READY (see MISSING above)")
    print("(missing artifacts above are expected work, not an environment problem)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
