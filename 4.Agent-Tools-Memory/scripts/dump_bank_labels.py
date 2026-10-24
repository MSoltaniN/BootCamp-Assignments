"""Dump every question's labels and answers, grouped by section."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bank = json.loads((ROOT / "docs" / "generated" / "question_bank.json").read_text(encoding="utf-8"))

lines: list[str] = []
for question in bank["questions"]:
    lines.append(f"[{question['id']}] pts={question['points']} status={question['status']}")
    for index, field in enumerate(question["fields"]):
        answer = field["answer"]
        if isinstance(answer, str) and len(answer) > 110:
            answer = answer[:110] + "..."
        lines.append(f"    {index} ({field['kind']:<8}) {field['label']}  =>  {answer!r}")
    lines.append("")

out = ROOT / "docs" / "generated" / "bank_dump.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out.name} questions={len(bank['questions'])} lines={len(lines)}")
