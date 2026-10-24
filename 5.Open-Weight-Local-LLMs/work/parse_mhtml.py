"""Parse the saved iCourse mission page (MHTML) into structured question data.

Outputs:
  work/assignment.json      -> structured (sections -> questions -> options)
  work/assignment_raw.md    -> human readable dump (Persian, RTL order preserved)
"""
from __future__ import annotations

import email
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MHTML = ROOT / "5_ iCourse.mhtml"
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)


def read_html() -> str:
    with MHTML.open("rb") as fh:
        msg = email.message_from_binary_file(fh)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    raise SystemExit("no text/html part found")


class MissionParser(HTMLParser):
    """Very small, purpose-built extractor for the mission page markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.brief_parts: list[str] = []
        self.sections: list[dict] = []
        self._mode: str | None = None
        self._depth = 0
        self._section: dict | None = None
        self._question: dict | None = None
        self._capture: str | None = None
        self._buf: list[str] = []
        self._seen_q = False

    # -- helpers -----------------------------------------------------
    def _flush(self) -> str:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf.clear()
        return text

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        cls = a.get("class", "")

        if tag == "h1" and "pageTitle" in cls:
            self._capture = "title"
            return
        if tag == "div" and "Markdown_md" in cls and not self._seen_q:
            self._capture = "brief"
            self._buf = []
            return
        if tag == "section" and "AssignmentForm_section" in cls:
            self._section = {"title": "", "points": "", "questions": []}
            self.sections.append(self._section)
            self._mode = "section"
            return
        if tag == "span" and self._mode == "section" and "secTitle" in cls:
            self._capture = "sec_title"
            self._buf = []
            return
        if tag == "article" and self._section is not None and a.get("id", "").startswith("q-"):
            self._section["questions"].append(
                {"id": a["id"][2:], "prompt": "", "options": [], "points": ""}
            )
            self._question = self._section["questions"][-1]
            self._seen_q = True
            return
        if self._question is None:
            return
        if tag == "span" and "qPts" in cls:
            self._capture = "pts"
            self._buf = []
            return
        if tag == "p" and "prompt" in cls:
            self._capture = "prompt"
            self._buf = []
            return
        if tag == "button" and a.get("role") == "radio":
            self._capture = "option"
            self._buf = []
            return

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "h1":
            self.title = self._flush()
            self._capture = None
        elif self._capture == "brief" and tag == "div":
            self.brief_parts.append(self._flush())
            self._capture = None
        elif self._capture == "sec_title" and tag == "span":
            assert self._section is not None
            self._section["title"] = self._flush()
            self._capture = None
        elif self._capture == "pts" and tag == "span":
            assert self._question is not None
            self._question["points"] = self._flush()
            self._capture = None
        elif self._capture == "prompt" and tag == "p":
            assert self._question is not None
            self._question["prompt"] = self._flush()
            self._capture = None
        elif self._capture == "option" and tag == "button":
            assert self._question is not None
            self._question["options"].append(self._flush())
            self._capture = None
        elif tag == "article" and self._question is not None:
            self._question = None
        elif tag == "section" and self._mode == "section":
            self._mode = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)


def main() -> None:
    raw = read_html()
    p = MissionParser()
    p.feed(raw)

    data = {
        "title": p.title,
        "brief": "\n\n".join(t for t in p.brief_parts if t),
        "sections": [s for s in p.sections if s["questions"]],
    }
    (WORK / "assignment.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [f"# {data['title']}", "", "## شرح تکلیف", "", data["brief"], ""]
    for i, sec in enumerate(data["sections"], 1):
        lines += [f"## بخش {i}: {sec['title']}", ""]
        for q in sec["questions"]:
            lines.append(f"### سوال {q['id']} ({q['points']})")
            lines.append("")
            lines.append(q["prompt"])
            lines.append("")
            for j, opt in enumerate(q["options"]):
                lines.append(f"  - [{j}] {opt}")
            lines.append("")
    (WORK / "assignment_raw.md").write_text("\n".join(lines), encoding="utf-8")

    total = sum(len(s["questions"]) for s in data["sections"])
    print(f"title={data['title']!r}")
    print(f"sections={len(data['sections'])} questions={total}")
    for i, sec in enumerate(data["sections"], 1):
        print(f"  {i}: {sec['title']!r} -> {len(sec['questions'])} q")


if __name__ == "__main__":
    main()
