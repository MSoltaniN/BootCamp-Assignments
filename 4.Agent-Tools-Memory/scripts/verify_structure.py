"""Verify that the project layout and generated artifacts are complete.

Checks folders, documents and generated files, and prints an ASCII report so it
stays readable on a cp1256 console.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

folders = [
    "assignment/source/Day4",
    "assignment/source/Day4/Day4_Datasets",
    "assignment/source/Day4/Day4_Grading",
    "assignment/source/Day4/Day4_Starter",
    "datasets",
    "docs",
    "docs/generated",
    "docs/generated/qa",
    "scripts",
    "work",
    "work/common",
    "work/sec05_data",
    "work/sec06_mcp",
    "work/sec07_loop",
    "work/sec08_memory",
    "work/sec09_routing",
    "work/sec10_security",
    "work/sec11_eval",
    "work/sec12_rollout",
    "Day4_Code",
    "Day4_Run_Output",
    "deliverables",
]

documents = [
    "README.md",
    "docs/00_roadmap.md",
    "docs/01_assignment_brief.md",
    "docs/02_data_map.md",
    "docs/03_rules_and_risks.md",
    "docs/04_environment.md",
    "docs/05_deliverables.md",
    "docs/06_answer_workflow.md",
    "work/README.md",
]

artifacts = [
    "docs/generated/questions.json",
    "docs/generated/questions.md",
    "docs/generated/question_bank.json",
    "docs/generated/answer_key.md",
    "docs/generated/assignment_text.txt",
    "docs/generated/qa/_extraction_report.txt",
    "docs/generated/qa/_data_probe.txt",
    "docs/generated/qa/_reconcile.txt",
    "docs/generated/qa/_nb_probe.txt",
]

code = [
    "scripts/extract_assignment.py",
    "scripts/verify_extraction.py",
    "scripts/probe_datasets.py",
    "scripts/reconcile_schema.py",
    "scripts/probe_notebook.py",
    "scripts/build_question_bank.py",
    "scripts/verify_structure.py",
    "work/common/__init__.py",
    "work/common/paths.py",
    "work/common/data.py",
    "work/common/principal.py",
    "work/smoke_test.py",
]


def main() -> int:
    missing_folders = [f for f in folders if not (ROOT / f).is_dir()]
    missing_docs = [f for f in documents if not (ROOT / f).is_file()]
    missing_artifacts = [f for f in artifacts if not (ROOT / f).is_file()]
    missing_code = [f for f in code if not (ROOT / f).is_file()]

    def section(title: str, missing: list[str], total: int) -> None:
        status = "ok  " if not missing else "FAIL"
        print(f"[{status}] {title:<12} {total - len(missing)}/{total}")
        for item in missing:
            print(f"        missing: {item}")

    print("== LAYOUT ==")
    section("folders", missing_folders, len(folders))
    section("documents", missing_docs, len(documents))
    section("artifacts", missing_artifacts, len(artifacts))
    section("code", missing_code, len(code))

    print("\n== BANK SANITY ==")
    bank_path = ROOT / "docs" / "generated" / "question_bank.json"
    if bank_path.is_file():
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        totals = bank["totals"]
        expectations = {
            "sections": 12,
            "questions": 144,
            "choice_fields": 120,
            "number_fields": 132,
            "short_fields": 64,
            "textarea_fields": 104,
        }
        failures = 0
        for key, expected in expectations.items():
            actual = totals[key]
            ok = actual == expected
            failures += 0 if ok else 1
            print(f"  [{'ok  ' if ok else 'FAIL'}] {key:<16} {actual}")
        points_ok = abs(totals["points"] - 100.0) < 1e-9
        failures += 0 if points_ok else 1
        print(f"  [{'ok  ' if points_ok else 'FAIL'}] {'points':<16} {totals['points']}")
        warnings_ok = not bank["warnings"]
        failures += 0 if warnings_ok else 1
        print(f"  [{'ok  ' if warnings_ok else 'FAIL'}] {'warnings':<16} {len(bank['warnings'])}")
    else:
        failures = 1
        print("  question_bank.json not found")

    print("\n== DATASET FILES ==")
    data_dir = ROOT / "assignment" / "source" / "Day4" / "Day4_Datasets"
    manifest_path = data_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing = [m["path"] for m in manifest if not (data_dir / m["path"]).is_file()]
        status = "ok  " if not missing else "FAIL"
        print(f"  [{status}] manifest-listed files present "
              f"{len(manifest) - len(missing)}/{len(manifest)}")
        for item in missing:
            print(f"        missing: {item}")
        failures += len(missing)
    else:
        print("  [FAIL] manifest.json not found")
        failures += 1

    print()
    if missing_folders or missing_docs or missing_artifacts or missing_code or failures:
        print("STRUCTURE CHECK FAILED")
        return 1
    print("STRUCTURE CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
