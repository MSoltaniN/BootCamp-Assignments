"""Build the evidence ZIP the site's second attachment card asks for.

Two things happen here:

1. `full_evidence.json` is assembled. `START_HERE.md` names that file
   explicitly, but nothing had produced it, so a grader looking for it would
   have found nothing. It is a single openable bundle of the numbers behind
   every practical answer.

2. The ZIP is written with a deterministic member order and a manifest of
   SHA-256 digests, so the grader can verify nothing changed after upload.

Deliberate exclusions: the payload/transfer scratch files used to fill the web
form, the snapshot of earlier artifacts, and any dataset. The pack asks that
shared datasets and binaries not be repeated in the submission.
"""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Day4_Run_Output"
DELIV = ROOT / "deliverables"
ZIP_PATH = DELIV / "Day4_Evidence.zip"

# Files at the ZIP root, in this order.
ROOT_FILES = [
    (OUT / "application.sqlite", "application.sqlite"),
    (OUT / "checkpoints.sqlite", "checkpoints.sqlite"),
    (OUT / "database_check.json", "database_check.json"),
    (OUT / "full_evidence.json", "full_evidence.json"),
    (OUT / "route_predictions.jsonl", "route_predictions.jsonl"),
    (OUT / "locked_router_config.json", "locked_router_config.json"),
    (OUT / "agent_trace.json", "agent_trace.json"),
    (OUT / "agent_card.json", "agent_card.json"),
    (OUT / "execution_scope.json", "execution_scope.json"),
    (OUT / "redteam_reports.json", "redteam_reports.json"),
    (OUT / "regression_gate.json", "regression_gate.json"),
    (OUT / "handoff_manifest.json", "handoff_manifest.json"),
    (OUT / "handoff_check.json", "handoff_check.json"),
    (OUT / "section5.json", "section5.json"),
    (OUT / "sections_6_12.json", "sections_6_12.json"),
    (OUT / "coverage_by_department.png", "coverage_by_department.png"),
    (OUT / "section5_console.log", "logs/section5_console.log"),
    (OUT / "sections_6_12_console.log", "logs/sections_6_12_console.log"),
    (OUT / "summary.txt", "logs/summary.txt"),
]

# My own code: the graded modules plus the pipelines that produced the numbers.
CODE_GLOBS = [
    ("Day4_Code/*.py", "code"),
    ("work/**/*.py", "code"),
]

# The Persian documentation set.
DOC_GLOBS = [("docs/*.md", "docs")]

# Never ship these.
EXCLUDED_PARTS = {
    "_snapshot_original", "__pycache__", ".pw-scratch", "temp",
    "form_payload_all.json", "form_payload_6_12.json", "form_payload_b64.txt",
    "fill.html", "payload_lines.txt", "chunk_0.txt", "chunk_1.txt", "chunk_2.txt",
}

LIMIT_SINGLE = 25 * 1024 * 1024
LIMIT_TOTAL = 50 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_full_evidence() -> Path:
    """One bundle containing every number a practical answer points at."""
    def load(name):
        path = OUT / name
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    s5 = load("section5.json") or {}
    s = load("sections_6_12.json") or {}
    checker = load("database_check.json") or {}
    manifest = load("handoff_manifest.json") or {}

    bundle = {
        "about": (
            "Consolidated evidence for Day 4. Every practical answer in the "
            "notebook reads its numbers from Day4_Run_Output/; this file is the "
            "same content in one place so a grader can open a single document."
        ),
        "generated_from": "Day4_Run_Output",
        "checker": {
            "status": checker.get("status"),
            "controls_passed": sum(1 for c in checker.get("checks", []) if c.get("passed")),
            "controls_total": len(checker.get("checks", [])),
            "note": checker.get("proof"),
        },
        "section5": s5,
        "section6": s.get("section6"),
        "section7": s.get("section7"),
        "section8": s.get("section8"),
        "section9": s.get("section9"),
        "section10": s.get("section10"),
        "section11": s.get("section11"),
        "section12": s.get("section12"),
        "handoff_check": s.get("handoff_check"),
        "delivery_manifest": manifest,
        "answer_totals": {
            "questions": (s.get("section12") or {}).get("weights", {}).get("questions"),
            "total_score": (s.get("section12") or {}).get("weights", {}).get("total_score"),
            "practical_answers": (s.get("section12") or {}).get("practical_answers"),
            "test_predictions": (s.get("section12") or {}).get("test_predictions"),
            "security_controls": (s.get("section12") or {}).get("security_controls"),
        },
    }

    target = OUT / "full_evidence.json"
    target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return target


def write_readme(members: list[str]) -> Path:
    """The replay README the pack asks for, in Persian."""
    body = """# بستهٔ شواهد — تکلیف ۴

## بازتولید

از ریشهٔ پروژه (جایی که `Day4_Code/` هست):

```
python -m venv .venv
.venv\\Scripts\\python.exe -m pip install --no-cache-dir -r assignment\\source\\Day4\\requirements-day4.txt
.venv\\Scripts\\python.exe work\\sec06_12_pipeline\\run_all.py        # بخش‌های ۶ تا ۱۲
.venv\\Scripts\\python.exe work\\sec05_data\\run_section5.py          # بخش ۵
.venv\\Scripts\\python.exe assignment\\source\\Day4\\Day4_Grading\\check_submission.py ^
    --application-db Day4_Run_Output\\application.sqlite ^
    --checkpoint-db Day4_Run_Output\\checkpoints.sqlite ^
    --output Day4_Run_Output\\database_check.json
```

اجرای بخش‌های ۶ تا ۱۲ حدود ۲۰ ثانیه طول می‌کشد. `--root` را دستی تنظیم نکنید؛
مقدار پیش‌فرض همان `assignment/source/Day4` است که `Day4_Datasets/` را پیدا می‌کند.

## محتوا

| مسیر | توضیح |
|---|---|
| `application.sqlite` | پایگاه کاربرد با شش جدول: memories، profiles، approvals، writes، audit، jobs |
| `checkpoints.sqlite` | checkpoint پایدار LangGraph (پایگاه جدا) |
| `database_check.json` | نتیجهٔ checker همراه، **۱۴ از ۱۴** موفق |
| `full_evidence.json` | همهٔ اعداد بخش‌های ۵ تا ۱۲ در یک سند |
| `route_predictions.jsonl` | ۸۰ پیش‌بینی آزمون مسیریاب قفل‌شده |
| `locked_router_config.json` | پیکربندی قفل‌شده (تنظیم فقط با dev) |
| `agent_trace.json` | رد اجرای حلقه |
| `agent_card.json` | کارت ایجنت با ۱۰ فیلد الزامی |
| `execution_scope.json` | تفکیک اجراشدهٔ واقعی / fixture / اجرانشده |
| `redteam_reports.json` | ده خانوادهٔ تهدید و کنترل هرکدام |
| `regression_gate.json` | دروازهٔ کیفیت روی dev |
| `handoff_manifest.json` | SHA-256 و اندازهٔ فایل‌های کلیدی |
| `handoff_check.json` | جمع‌بندی تحویل |
| `section5.json` / `sections_6_12.json` | خروجی عددی بخش‌ها |
| `code/` | ماژول‌های `Day4_Code` و خط‌لولهٔ `work` |
| `docs/` | مستندات فارسی، شامل نقشهٔ کد و گزارش بخش‌ها |

## نکات صادقانه

- تصمیم‌گیر و لاگ‌ها **fixture** هستند؛ هیچ LLM زنده‌ای اجرا نشده است
  (`execution_scope.json`).
- A2A و احراز هویت سازمانی پیاده نشده‌اند و ادعا هم نمی‌شوند.
- آزمون جفت‌شدهٔ test **معنادار نیست** (بازهٔ ۹۵٪ شامل صفر است) و همین‌طور گزارش شده.
- `checker_passed` در `handoff_manifest.json` مقدار `null` دارد، چون بررسی معتبر
  باید با نسخهٔ خودِ مدرس اجرا شود.
- هیچ رمز، توکن یا API key واقعی در این بسته نیست.

## اعتبارسنجی

`SHA256SUMS.txt` هش همهٔ اعضای بسته را دارد.
"""
    # Written outside `deliverables/` on purpose: the README belongs *inside*
    # the ZIP. Leaving a loose copy next to the archive only creates a third
    # file that has to be sent separately.
    path = ROOT / "docs" / "generated" / "_evidence_readme.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def collect() -> list[tuple[Path, str]]:
    members: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add(path: Path, arcname: str) -> None:
        if not path.is_file() or arcname in seen:
            return
        if any(part in EXCLUDED_PARTS for part in path.parts):
            return
        seen.add(arcname)
        members.append((path, arcname))

    for source, arcname in ROOT_FILES:
        add(source, arcname)

    for pattern, prefix in CODE_GLOBS + DOC_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            # Keep the relative path: `work/` holds seven different
            # `answers.py` files and a flat name would overwrite six of them.
            relative = path.relative_to(ROOT)
            add(path, f"{prefix}/{relative.as_posix()}")

    for path in sorted((OUT / "traces").glob("*")):
        add(path, f"traces/{path.name}")

    return members


def main() -> int:
    build_full_evidence()
    readme = DELIV / "README_evidence.md"
    write_readme([])

    members = collect()
    members.append((readme, "README.md"))

    missing = [arc for src, arc in ROOT_FILES if not src.is_file()]
    if missing:
        print("warning: absent from run output:", missing)

    DELIV.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, arcname in members:
            archive.write(path, arcname)
        sums = "".join(f"{sha256(p)}  {a}\n" for p, a in members)
        archive.writestr("SHA256SUMS.txt", sums)

    total_zip = ZIP_PATH.stat().st_size
    largest = max((p.stat().st_size for p, _ in members), default=0)

    print(f"members        : {len(members) + 1}")
    print(f"largest member : {largest / 1048576:.2f} MiB")
    print(f"zip size       : {total_zip / 1048576:.2f} MiB  ({total_zip} bytes)")
    print(f"single limit   : {'OK' if largest <= LIMIT_SINGLE else 'OVER 25 MiB'}")
    print(f"zip limit      : {'OK' if total_zip <= LIMIT_SINGLE else 'OVER 25 MiB'}")
    print(f"combined limit : {'OK' if total_zip <= LIMIT_TOTAL else 'OVER 50 MiB'}")
    print(f"written        : {ZIP_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
