"""
Extract the assignment brief and the full question bank from the saved iCourse
mission page (`4_ iCourse.mhtml`) using only the Python standard library.

The MHTML export stores the page as MIME parts. The HTML part is encoded with
quoted-printable, so every Persian character arrives as `=D8=AA` style escapes
and long tags are folded with soft line breaks. Decoding yields ordinary
(minified) HTML, which is then picked apart with targeted regular expressions.

Page structure that matters
---------------------------
<sections>          -> "بخش N" blocks, each worth 6/8/10 points
  <question>        -> <article id="q-N.M">, each worth 0.5 or 1 point
    <field>         -> <div id="N.M-K-l"> radio group, <label for="N.M-K">
                       input, or <textarea id="N.M-K"> free text

A few questions are pure free text (single textarea); most mix "yes/no" radio
fields with a textarea that must carry the code and the analysis.

Outputs
-------
docs/assignment_text.txt   plain UTF-8 rendering of the page body
docs/questions.json        sections + questions + typed fields
docs/questions.md          the same bank as a readable Persian checklist

Usage
-----
    python scripts/extract_assignment.py [path/to/mhtml]
"""

from __future__ import annotations

import json
import quopri
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "4_ iCourse.mhtml"
DOCS = ROOT / "docs" / "generated"

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# U+066B ARABIC DECIMAL SEPARATOR is what the page uses for "0٫5".
PERSIAN_SEPARATORS = str.maketrans({"\u066b": ".", "\u060c": ","})


# --------------------------------------------------------------------------
# decoding helpers
# --------------------------------------------------------------------------
class _TextCollector(HTMLParser):
    """Collect visible text from a fragment, dropping tags and inline SVG."""

    SKIP = {
        "script", "style", "svg", "path", "circle", "rect", "line", "g",
        "mask", "polyline", "defs", "linearGradient", "stop",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: D102
        if tag in self.SKIP or tag == "linearGradient":
            self._depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: D102
        return

    def handle_endtag(self, tag: str) -> None:  # noqa: D102
        if (tag in self.SKIP or tag == "linearGradient") and self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:  # noqa: D102
        if not self._depth:
            self.chunks.append(data)

    def text(self, collapse: bool = True) -> str:
        raw = "".join(self.chunks)
        raw = raw.replace("\u200f", "").replace("\u200e", "")
        if collapse:
            return re.sub(r"\s+", " ", raw).strip()
        return raw


def strip_tags(fragment: str) -> str:
    parser = _TextCollector()
    parser.feed(fragment)
    parser.close()
    return parser.text()


def strip_tags_lines(fragment: str) -> str:
    parser = _TextCollector()
    parser.feed(fragment)
    parser.close()
    raw = parser.text(collapse=False)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    return "\n".join(lines)


def norm_digits(value: str) -> str:
    """Map Persian/Arabic digits and separators to ASCII."""
    return (
        value.translate(PERSIAN_DIGITS)
        .translate(ARABIC_DIGITS)
        .translate(PERSIAN_SEPARATORS)
    )


def decode_mhtml(raw: bytes) -> str:
    """Return the decoded HTML document carried by the MHTML container."""
    text = raw.decode("utf-8", errors="replace")
    boundary = re.search(r'boundary="([^"]+)"', text)
    parts = re.split(re.escape(boundary.group(1)), text) if boundary else [text]

    bodies: list[str] = []
    for part in parts:
        if "quoted-printable" not in part.lower():
            continue
        split = re.split(r"\r?\n\r?\n", part, maxsplit=1)
        if len(split) == 2:
            bodies.append(split[1])

    target = max(bodies, key=len) if bodies else text
    decoded = quopri.decodestring(target.encode("utf-8", errors="replace"))
    return decoded.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# structural parsing
# --------------------------------------------------------------------------
def _search(pattern: str, haystack: str, group: int = 1) -> str:
    match = re.search(pattern, haystack, re.S)
    return match.group(group) if match else ""


def parse_page_title(html: str) -> str:
    return strip_tags(_search(r'class="ui_pageTitle[^"]*"[^>]*>(.*?)</h1>', html))


def parse_facts(html: str) -> dict[str, str]:
    keys = re.findall(r'class="Missions_factKey[^"]*">(.*?)</span>', html, re.S)
    values = re.findall(r'class="Missions_factVal[^"]*">(.*?)</span>', html, re.S)
    facts = {}
    for key, value in zip(keys, values):
        facts[norm_digits(strip_tags(key))] = norm_digits(strip_tags(value))
    return facts


def parse_pack_link(html: str) -> str:
    return _search(r'href="([^"]+\.zip)"', html)


def parse_brief(html: str) -> str:
    """The 'شرح تکلیف' panel lives before the form."""
    head = html.split("AssignmentForm_wrap", 1)[0]
    block = _search(r'class="Markdown_md[^"]*">(.*?)</div>', head)
    if not block:
        return ""
    fragment = re.sub(r"<li[^>]*>", "\n- ", block)
    fragment = re.sub(r"</li>", "", fragment)
    fragment = re.sub(r"</p>", "\n\n", fragment)
    return re.sub(r"\n{3,}", "\n\n", strip_tags_lines(fragment)).strip()


SECTION_RE = re.compile(r'<section class="[^"]*AssignmentForm_section[^"]*"[^>]*>')


def parse_sections(html: str) -> list[dict]:
    starts = [m.start() for m in SECTION_RE.finditer(html)]
    sections: list[dict] = []
    for index, offset in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(html)
        block = html[offset:end]
        header = block.split("AssignmentForm_questions", 1)[0]
        sections.append(
            {
                "number": norm_digits(
                    strip_tags(_search(r'class="AssignmentForm_secNo[^"]*">(.*?)</span>', header))
                ),
                "title": strip_tags(
                    _search(r'class="AssignmentForm_secTitle[^"]*">(.*?)</span>', header)
                ),
                "meta": norm_digits(
                    strip_tags(_search(r'class="AssignmentForm_secMeta[^"]*">(.*?)</span>', header))
                ),
                "intro": strip_tags(
                    _search(r'class="AssignmentForm_intro[^"]*">(.*?)</p>', block)
                ),
            }
        )
    return sections


QUESTION_RE = re.compile(r'<article id="q-([\d.]+)"')


def parse_fields(block: str) -> list[dict]:
    """Extract every input slot of one question, in document order.

    Slots come in three shapes:

      * `<span ... id="5.6-0-l">LABEL</span> ... role="radiogroup"`  -> radio
      * `<label ... for="5.6-1"><span ...>LABEL</span><input ...>`  -> input
      * `<label ...><span ...>LABEL</span><textarea id="5.6-2">`    -> textarea

    The label text is the human description of what the slot expects.
    """
    # Keep the ordered list of control positions so fields stay in page order.
    markers: list[tuple[int, str, str]] = []  # (offset, kind, field_id)

    for match in re.finditer(r'id="([\d.]+-\d+)-l"', block):
        markers.append((match.start(), "radio", match.group(1)))
    for match in re.finditer(r'<label[^>]*for="([\d.]+-\d+)"', block):
        # Distinguish input vs textarea by looking at the label body.
        tail = block[match.start() : match.start() + 4000]
        kind = "textarea" if "<textarea" in tail.split("</label>", 1)[0] else "input"
        markers.append((match.start(), kind, match.group(1)))
    for match in re.finditer(r'<textarea id="([\d.]+-\d+)"', block):
        if not any(fid == match.group(1) for _, _, fid in markers):
            markers.append((match.start(), "textarea", match.group(1)))

    markers.sort(key=lambda item: item[0])

    fields: list[dict] = []
    for position, (offset, kind, field_id) in enumerate(markers):
        if kind == "radio":
            label = strip_tags(_search(r'id="' + re.escape(field_id) + r'-l"[^>]*>(.*?)</span>', block))
            group_start = block.find("radiogroup", offset)
            group = block[group_start:] if group_start != -1 else ""
            group = group.split("</div>", 1)[0]
            choices = [
                strip_tags(raw)
                for raw in re.findall(r'role="radio"[^>]*>(.*?)</button>', group, re.S)
            ]
            fields.append(
                {"id": field_id, "kind": "radio", "label": label,
                 "choices": [c for c in choices if c]}
            )
            continue

        label = strip_tags(
            _search(r'(?:for="' + re.escape(field_id) + r'"[^>]*>)(.*?)</(?:span|label)>', block)
        )
        if not label:
            label = strip_tags(
                _search(r'<span class="AssignmentForm_label[^"]*"[^>]*>(.*?)</span>', block)
            )
        placeholder = _search(r'id="' + re.escape(field_id) + r'"[^>]*placeholder="([^"]*)"', block)
        fields.append(
            {
                "id": field_id,
                "kind": kind,
                "label": label,
                "choices": [],
                "placeholder": strip_tags(placeholder) if placeholder else "",
            }
        )

    # De-duplicate while keeping order (labels and controls can both match).
    seen: set[str] = set()
    unique: list[dict] = []
    for field in fields:
        if field["id"] in seen:
            continue
        seen.add(field["id"])
        unique.append(field)
    return unique


def parse_questions(html: str) -> list[dict]:
    anchors = [(m.start(), m.group(1)) for m in QUESTION_RE.finditer(html)]
    questions: list[dict] = []
    for index, (offset, qid) in enumerate(anchors):
        end = anchors[index + 1][0] if index + 1 < len(anchors) else len(html)
        block = html[offset:end]

        fields = parse_fields(block)
        prompt = strip_tags(_search(r'class="AssignmentForm_prompt[^"]*">(.*?)</p>', block))
        points_raw = norm_digits(
            strip_tags(_search(r'class="AssignmentForm_qPts[^"]*">(.*?)</span>', block))
        )
        points = 0.0
        number = _search(r"([\d.]+)", points_raw)
        if number:
            try:
                points = float(number)
            except ValueError:
                points = 0.0

        radio_fields = [f for f in fields if f["kind"] == "radio"]
        text_fields = [f for f in fields if f["kind"] in {"input", "textarea"}]

        if radio_fields and text_fields:
            qtype = "mixed"
        elif radio_fields:
            qtype = "single_choice_set"
        else:
            qtype = "free_text"

        questions.append(
            {
                "id": qid,
                "section": qid.split(".")[0],
                "points": points,
                "points_label": points_raw,
                "type": qtype,
                "prompt": prompt,
                "fields": fields,
                "radio_pairs": len(radio_fields),
                "text_slots": len(text_fields),
                "answers": {f["id"]: None for f in fields},
                "rationale": None,
                "code_cells": [],
            }
        )
    return questions


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        print(f"source not found: {source}")
        return 1

    html = decode_mhtml(source.read_bytes())
    DOCS.mkdir(parents=True, exist_ok=True)

    title = parse_page_title(html)
    facts = parse_facts(html)
    pack = parse_pack_link(html)
    brief = parse_brief(html)
    sections = parse_sections(html)
    questions = parse_questions(html)

    body = html.split('<div id="ic-main"', 1)[-1]
    text = re.sub(r"\n{3,}", "\n\n", strip_tags_lines(body))
    (DOCS / "assignment_text.txt").write_text(text.strip() + "\n", encoding="utf-8")

    total_points = sum(q["points"] for q in questions)
    bank = {
        "source_page": (
            "https://shokrzad.com/ai/icourse/ai-agents-bootcamp/"
            "missions/3ac7676d-c509-44d2-8dd5-9380496544e3"
        ),
        "title": title,
        "facts": facts,
        "student_pack": pack,
        "brief": brief,
        "totals": {
            "sections": len(sections),
            "questions": len(questions),
            "points": total_points,
            "radio_fields": sum(q["radio_pairs"] for q in questions),
            "text_slots": sum(q["text_slots"] for q in questions),
        },
        "sections": sections,
        "questions": questions,
    }
    (DOCS / "questions.json").write_text(
        json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DOCS / "questions.md").write_text(render_markdown(bank), encoding="utf-8")

    def say(label: str, value: object) -> None:
        print(f"{label:<11}: {value}")

    say("title", title.encode("ascii", "backslashreplace").decode("ascii"))
    say("sections", len(sections))
    say("questions", len(questions))
    say("points", total_points)
    say("radio", bank["totals"]["radio_fields"])
    say("textslots", bank["totals"]["text_slots"])
    say("pack", pack)
    missing = [q["id"] for q in questions if not q["prompt"]]
    if missing:
        say("WARN prompt", missing)
    no_fields = [q["id"] for q in questions if not q["fields"]]
    if no_fields:
        say("WARN fields", no_fields)
    return 0


def render_markdown(bank: dict) -> str:
    lines = [f"# {bank['title']}", ""]
    if bank["facts"]:
        lines.append("## مشخصات تکلیف")
        lines += [f"- **{key}:** {value}" for key, value in bank["facts"].items()]
        lines.append("")
    if bank["student_pack"]:
        lines += [f"- **بسته دانشجو:** <{bank['student_pack']}>", ""]
    if bank["brief"]:
        lines += ["## شرح تکلیف", "", bank["brief"], ""]

    lines.append("## جمع‌بندی")
    totals = bank["totals"]
    lines += [
        f"- تعداد بخش‌ها: {totals['sections']}",
        f"- تعداد زیرسؤال‌ها: {totals['questions']}",
        f"- مجموع نمره: {totals['points']}",
        f"- فیلدهای بله/خیر: {totals['radio_fields']}",
        f"- جایگاه‌های متن/کد: {totals['text_slots']}",
        "",
    ]

    by_section: dict[str, list[dict]] = {}
    for question in bank["questions"]:
        by_section.setdefault(question["section"], []).append(question)

    for section in bank["sections"]:
        number = section["number"]
        group = by_section.get(number, [])
        section_points = sum(q["points"] for q in group)
        lines.append(f"## بخش {number} — {section['title']} ({section_points:g} نمره)")
        if section["meta"]:
            lines.append(f"> داده/منبع: {section['meta']}")
        if section["intro"]:
            lines.append(f"\n*{section['intro']}*")
        lines.append("")

        for question in group:
            lines.append(f"### زیرسؤال {question['id']} ({question['points']:g} نمره)")
            lines.append(question["prompt"])
            lines.append("")
            for field in question["fields"]:
                if field["kind"] == "radio":
                    options = " / ".join(field["choices"])
                    lines.append(f"- [ ] **{field['label']}** — {options}")
                else:
                    lines.append(f"- [ ] **{field['label']}** _(کد + خروجی + تحلیل فارسی)_")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
