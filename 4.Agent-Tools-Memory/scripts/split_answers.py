"""Split the section 6-12 answer module into one file per section.

Reads the existing combined modules and writes:

    work/sec06_mcp/answers.py
    work/sec07_loop/answers.py
    ...
    work/sec12_rollout/answers.py

Each file exports `FIELD_ANSWERS` and `RATIONALE` for its own section only, so a
reviewer can open one folder and see exactly that section's answers.

Run once, then delete the source module.
"""

from __future__ import annotations

import pprint
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

from sec06_12_answers.answers import FIELD_ANSWERS  # noqa: E402
from sec06_12_answers.rationale_6_8 import RATIONALE as R68  # noqa: E402
from sec06_12_answers.rationale_9_12 import RATIONALE as R912  # noqa: E402

RATIONALE = {**R68, **R912}

FOLDERS = {
    "6": ("sec06_mcp", "ابزارهای محدود و اتصال واقعی MCP"),
    "7": ("sec07_loop", "حلقهٔ ابزار و توقف قابل آزمون"),
    "8": ("sec08_memory", "حافظهٔ پایدار و تأیید انسانی"),
    "9": ("sec09_router", "مسیریابی و معماری چندنقشی"),
    "10": ("sec10_security", "دفاع چندلایه و ده آزمون تهدید"),
    "11": ("sec11_eval", "ارزیابی نتیجه و مسیر و مشاهده‌پذیری"),
    "12": ("sec12_rollout", "انتشار کنترل‌شده و تحویل قابل تصحیح"),
}


def main() -> int:
    for number, (folder, title) in FOLDERS.items():
        prefix = f"{number}."

        fields = {k: v for k, v in FIELD_ANSWERS.items() if k[0].startswith(prefix)}
        rationales = {k: v for k, v in RATIONALE.items() if k.startswith(prefix)}

        if not fields or not rationales:
            print(f"section {number}: EMPTY (fields={len(fields)}, rat={len(rationales)})")
            return 1

        body = [
            f'"""بخش {number} — {title}',
            "",
            f"پاسخ‌ها از اجرای `work/sec06_12_pipeline/run_all.py` آمده‌اند.",
            f'"""',
            "",
            "from __future__ import annotations",
            "",
            "FIELD_ANSWERS: dict[tuple[str, int], object] = "
            + pprint.pformat(fields, width=96, sort_dicts=False),
            "",
            "RATIONALE: dict[str, str] = "
            + pprint.pformat(rationales, width=96, sort_dicts=False),
            "",
        ]

        target = ROOT / "work" / folder / "answers.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(body), encoding="utf-8")
        print(f"section {number:>2}: {len(fields):>3} fields, {len(rationales):>2} rationales -> {folder}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
