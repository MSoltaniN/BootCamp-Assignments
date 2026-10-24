"""Fill the iCourse assignment form from the local answer bank.

This uses the same technique that worked for section 5, just batched and driven
from the JSON instead of hand-pasted values:

  * text inputs / textareas: set through the native value setter so React sees
    the change, then dispatch `input` and `change`
  * radio groups: click the button whose visible text matches the answer

Nothing is submitted. The form auto-saves each field as a draft.

Run:
    .venv\\Scripts\\python.exe work/fill_form.py --sections 6 7 8 9 10 11 12
    .venv\\Scripts\\python.exe work/fill_form.py --sections 1 2 3 4
    .venv\\Scripts\\python.exe work/fill_form.py --audit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Playwright writes browser profiles and artifacts under %TEMP%, which is not
# writable in this environment. Redirect both to a project-local folder.
SCRATCH = Path(__file__).resolve().parents[1] / ".pw-scratch"
(SCRATCH / "temp").mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = str(SCRATCH / "temp")
os.environ["TMP"] = str(SCRATCH / "temp")

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "Day4_Run_Output" / "form_payload_all.json"
REPORT = ROOT / "Day4_Run_Output" / "form_fill_report.json"
URL = (
    "https://shokrzad.com/ai/icourse/ai-agents-bootcamp/"
    "missions/3ac7676d-c509-44d2-8dd5-9380496544e3"
)

# Runs inside the page. Fills one question by field id.
FILL_QUESTION = """
(args) => {
  const { qid, fields, dryRun } = args;
  const article = document.getElementById('q-' + qid);
  if (!article) return { qid, error: 'article missing' };

  const setText = (el, value) => {
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, String(value));
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };

  const results = [];
  for (const [fieldId, spec] of Object.entries(fields)) {
    const answer = spec.answer;
    if (answer === null || answer === undefined || answer === '') {
      results.push({ fieldId, status: 'skip-empty' });
      continue;
    }

    if (spec.kind === 'choice') {
      const group = article.querySelector(
        '[role="radiogroup"][aria-labelledby="' + fieldId + '-l"]'
      );
      if (!group) { results.push({ fieldId, status: 'no-group' }); continue; }
      const wanted = String(answer).trim();
      const button = [...group.querySelectorAll('[role="radio"]')]
        .find(b => b.textContent.trim() === wanted);
      if (!button) { results.push({ fieldId, status: 'no-option', wanted }); continue; }
      if (!dryRun) button.click();
      results.push({ fieldId, status: 'radio', value: wanted });
      continue;
    }

    const el = document.getElementById(fieldId);
    if (!el) { results.push({ fieldId, status: 'no-input' }); continue; }
    if (!dryRun) setText(el, answer);
    results.push({
      fieldId,
      status: 'text',
      len: String(answer).length,
      ok: dryRun ? true : el.value === String(answer),
    });
  }

  return { qid, answered: article.getAttribute('data-answered'), results };
}
"""

READ_QUESTION = """
(qid) => {
  const article = document.getElementById('q-' + qid);
  if (!article) return { qid, error: 'missing' };
  const labels = {};
  for (const el of article.querySelectorAll('input,textarea')) {
    const parent = el.closest('label') || el.parentElement;
    const span = parent && parent.querySelector('[class*="AssignmentForm_label"]');
    labels[el.id] = span ? span.textContent.trim() : '';
  }
  const radios = {};
  for (const group of article.querySelectorAll('[role="radiogroup"]')) {
    const fieldId = group.getAttribute('aria-labelledby').replace(/-l$/, '');
    const selected = [...group.querySelectorAll('[role="radio"]')]
      .filter(b => b.getAttribute('aria-checked') === 'true')
      .map(b => b.textContent.trim());
    radios[fieldId] = selected.join('|');
  }
  const values = {};
  for (const el of article.querySelectorAll('input,textarea')) {
    values[el.id] = el.value;
  }
  return {
    qid,
    answered: article.getAttribute('data-answered'),
    labels,
    radios,
    values,
  };
}
"""


def read_payload() -> dict:
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


def wanted_ids(payload: dict, sections: list[str] | None) -> list[str]:
    if not sections:
        return sorted(payload, key=lambda q: [int(x) for x in q.split(".")])
    return sorted(
        (q for q in payload if q.split(".")[0] in sections),
        key=lambda q: [int(x) for x in q.split(".")],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sections", nargs="*", default=None,
                        help="limit to these section numbers, e.g. 6 7 8")
    parser.add_argument("--audit", action="store_true",
                        help="read the form back instead of writing")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = read_payload()
    ids = wanted_ids(payload, args.sections)
    print(f"questions to process: {len(ids)}  audit={args.audit}")

    report: dict = {"mode": "audit" if args.audit else "fill", "questions": {}}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=0)
        context = browser.new_context(viewport={"width": 1500, "height": 950})
        page = context.new_page()

        print("opening form…")
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_selector("article[id^='q-']", timeout=60_000)

        # Sections render collapsed; expand every one before touching fields.
        try:
            page.get_by_role("button", name="باز کردن همه").click(timeout=8000)
        except Exception:
            pass
        page.wait_for_function(
            "() => document.querySelectorAll('article[id^=\"q-\"]').length === 144",
            timeout=30_000,
        )
        print("all 144 questions rendered")

        problems: list[str] = []
        for question_id in ids:
            fields = payload[question_id]
            if args.audit:
                observed = page.evaluate(READ_QUESTION, question_id)
                expected = {}
                for field_id, spec in fields.items():
                    answer = spec["answer"]
                    if spec["kind"] == "choice":
                        expected[field_id] = str(answer).strip() if answer else ""
                    else:
                        expected[field_id] = str(answer) if answer is not None else ""
                mismatches = []
                for field_id, want in expected.items():
                    got = observed["radios"].get(field_id, observed["values"].get(field_id))
                    if got is None:
                        continue
                    if str(got).strip() != want.strip():
                        mismatches.append({
                            "field": field_id,
                            "label": observed["labels"].get(field_id, ""),
                            "expected_len": len(want),
                            "got_len": len(str(got)),
                            "head": (want[:40] if want else ""),
                        })
                report["questions"][question_id] = {
                    "answered": observed.get("answered"),
                    "mismatches": mismatches,
                }
                if mismatches or observed.get("answered") != "true":
                    problems.append(question_id)
                continue

            outcome = page.evaluate(
                FILL_QUESTION,
                {"qid": question_id, "fields": fields, "dryRun": args.dry_run},
            )
            report["questions"][question_id] = outcome
            bad = [
                r for r in outcome.get("results", [])
                if r["status"] not in {"text", "radio", "skip-empty"}
                or r.get("ok") is False
            ]
            if bad or outcome.get("answered") != "true":
                problems.append(f"{question_id}:{bad[:2]}")

        bar = page.evaluate(
            "() => (document.querySelector('[class*=\"AssignmentForm_barText\"]')||{}).textContent"
        )
        report["progress_bar"] = bar
        report["problem_questions"] = problems
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"bar: {bar}")
        print(f"problems: {len(problems)}")
        for item in problems[:15]:
            print("  -", str(item)[:140])
        print(f"report: {REPORT.name}")

        browser.close()

    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
