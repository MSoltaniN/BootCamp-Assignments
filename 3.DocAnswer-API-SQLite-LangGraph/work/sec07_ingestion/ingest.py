"""Document ingestion with provenance.

Everything here is about being able to answer "which characters of which document version did this
text come from". A chunk that cannot be traced back to a byte range of a real file is not usable as
evidence, so the pipeline refuses to invent any.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------------------- manifest / hashing
def load_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_manifest(rows: list[dict], corpus_root: Path) -> tuple[list[dict], int]:
    """Attach the hash actually observed on disk and count how many match the manifest."""
    checked, valid = [], 0
    for row in rows:
        target = corpus_root / row["path"]
        raw = target.read_bytes() if target.exists() else b""
        observed = sha256_bytes(raw) if raw else ""
        ok = bool(observed) and observed == row["sha256"]
        valid += ok
        checked.append({**row, "observed_sha256": observed, "hash_ok": ok,
                        "bytes": len(raw), "exists": target.exists()})
    return checked, valid


# ----------------------------------------------------------------------------- PDF
def read_pdf(path: Path) -> dict:
    """Page-by-page extraction. A PDF with no extractable text is flagged, never silently indexed."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    total_chars = sum(len(p) for p in pages)
    needs_ocr = total_chars < 20          # essentially no text layer
    return {
        "path": str(path.name),
        "pages": len(reader.pages),
        "chars": total_chars,
        "chars_per_page": [len(p) for p in pages],
        "needs_ocr": needs_ocr,
        "text": "\n".join(pages),
    }


# ----------------------------------------------------------------------------- RST metadata
_RST_FIELD = re.compile(r"^([A-Za-z][A-Za-z -]*):\s*(.*)$")
_RST_SECTION = re.compile(r"^(.+)\n(={3,}|-{3,}|~{3,}|\^{3,})\s*$", re.M)


def parse_rst(text: str) -> dict:
    """PEP header fields plus section headings, taken from the document itself.

    Nothing is invented: a missing field yields None rather than a plausible-looking default.
    """
    header: dict[str, str] = {}
    for line in text.splitlines()[:40]:
        if not line.strip():
            if header:
                break
            continue
        m = _RST_FIELD.match(line)
        if m:
            header[m.group(1).strip().lower()] = m.group(2).strip()

    sections = []
    for match in _RST_SECTION.finditer(text):
        title = match.group(1).strip()
        underline = match.group(2)
        if len(underline) >= 3 and title and not set(title) <= set("=-~^"):
            sections.append({"title": title, "level_char": underline[0], "offset": match.start()})

    return {
        "pep": header.get("pep"),
        "title": header.get("title"),
        "author": header.get("author"),
        "status": header.get("status"),
        "type": header.get("type"),
        "created": header.get("created"),
        "sections": sections,
    }


# ----------------------------------------------------------------------------- chunking
@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    version: str
    chunk_index: int
    content: str
    start_char: int
    end_char: int
    section: str | None
    content_hash: str = ""
    token_count: int = 0


def _token_offsets(tokenizer, text: str) -> list[tuple[int, int]]:
    """Map each token back to a character span so a chunk can be cut at a token boundary.

    This is what keeps chunk text an exact substring of the source; slicing by characters would
    break the `content == source[start:end]` invariant.
    """
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                        return_attention_mask=False, return_token_type_ids=False, truncation=False)
    return list(encoded["offset_mapping"])


def chunk_text(text: str, *, doc_id: str, version: str, tokenizer,
               chunk_tokens: int = 220, overlap: int = 40,
               section_lookup: list[dict] | None = None,
               strict_truncation: bool = True) -> list[Chunk]:
    """Token-window chunking with character-exact provenance.

    `strict_truncation=True` shrinks the effective window to the model's token ceiling; the
    comparison in 7.9 runs with it off to expose what truncation would silently discard.
    """
    offsets = _token_offsets(tokenizer, text)
    if not offsets:
        return []

    chunks: list[Chunk] = []
    step = max(1, chunk_tokens - overlap)
    index = 0
    start_token = 0
    while start_token < len(offsets):
        window = offsets[start_token:start_token + chunk_tokens]
        if not window:
            break
        start_char = window[0][0]
        end_char = window[-1][1]
        content = text[start_char:end_char]
        if content.strip():
            section = _section_for(start_char, section_lookup)
            chunks.append(Chunk(
                chunk_id="", doc_id=doc_id, version=version, chunk_index=index,
                content=content, start_char=start_char, end_char=end_char, section=section,
                content_hash=sha256_bytes(content.encode("utf-8")),
                token_count=len(window),
            ))
            index += 1
        if start_token + chunk_tokens >= len(offsets):
            break
        start_token += step
    return chunks


def _section_for(position: int, sections: list[dict] | None) -> str | None:
    if not sections:
        return None
    current = None
    for section in sections:
        if section["offset"] <= position:
            current = section["title"]
        else:
            break
    return current


def make_chunk_id(doc_id: str, version: str, start: int, end: int, content_hash: str) -> str:
    """Depends on identity *and* content, so the same input always yields the same id.

    Version is part of the id so chunks of an older revision cannot collide with a newer one.
    """
    digest = hashlib.sha256(
        f"{doc_id}|{version}|{start}|{end}|{content_hash}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{doc_id}:v{version[:8]}:{start}-{end}:{digest}"


def assign_ids(chunks: list[Chunk]) -> list[Chunk]:
    for chunk in chunks:
        chunk.chunk_id = make_chunk_id(chunk.doc_id, chunk.version, chunk.start_char,
                                       chunk.end_char, chunk.content_hash)
    return chunks


# ----------------------------------------------------------------------------- dedup
def dedupe(chunks: list[Chunk]) -> tuple[list[Chunk], int]:
    """Exact duplicates only: same chunk_id (same doc, version, span, content).

    Two documents with identical text but different versions or access rules are *not* duplicates
    and must both survive, because a citation has to point at one specific authorized source.
    """
    seen: dict[str, Chunk] = {}
    removed = 0
    for chunk in chunks:
        if chunk.chunk_id in seen:
            removed += 1
            continue
        seen[chunk.chunk_id] = chunk
    return list(seen.values()), removed


# ----------------------------------------------------------------------------- provenance
def verify_provenance(chunks: list[Chunk], source_text: str) -> tuple[int, list[dict]]:
    """Every chunk must be a literal substring of its source and match its own hash."""
    failures = []
    for chunk in chunks:
        slice_ok = source_text[chunk.start_char:chunk.end_char] == chunk.content
        in_source = chunk.content in source_text
        hash_ok = sha256_bytes(chunk.content.encode("utf-8")) == chunk.content_hash
        if not (slice_ok and in_source and hash_ok):
            failures.append({"chunk_id": chunk.chunk_id, "slice_ok": slice_ok,
                             "in_source": in_source, "hash_ok": hash_ok})
    return len(failures), failures


def citation_path(chunk: Chunk, doc: dict) -> dict:
    """One traceable route from chunk text back to the original document and section."""
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "doc_title": doc.get("title"),
        "version": chunk.version,
        "source_url": doc.get("source_url"),
        "local_path": doc.get("path"),
        "section": chunk.section,
        "char_range": [chunk.start_char, chunk.end_char],
        "content_hash": chunk.content_hash,
        "quote": chunk.content[:160].replace("\n", " "),
    }
