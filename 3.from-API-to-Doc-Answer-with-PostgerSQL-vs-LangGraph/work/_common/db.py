"""SQLite helpers shared by every section: connection, schema, UPSERT.

SQLite does not enforce foreign keys unless `PRAGMA foreign_keys=ON` is set *per connection*;
every helper here does it, because forgetting it is the single most common way this exercise fails.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    role         TEXT NOT NULL CHECK (role IN ('admin', 'student')),
    tenant       TEXT NOT NULL,
    display_name TEXT,
    synthetic    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cases (
    case_id    TEXT PRIMARY KEY,
    owner_id   TEXT NOT NULL REFERENCES users(user_id),
    topic      TEXT,
    summary    TEXT,
    synthetic  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL REFERENCES users(user_id),
    case_id         TEXT NOT NULL REFERENCES cases(case_id),
    idempotency_key TEXT UNIQUE,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    content    TEXT NOT NULL,
    role       TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    version      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    title        TEXT,
    path         TEXT,
    source_url   TEXT,
    access       TEXT,
    tenant       TEXT,
    license      TEXT,
    source_type  TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id       TEXT PRIMARY KEY,
    doc_id         TEXT NOT NULL REFERENCES documents(doc_id),
    chunk_index    INTEGER NOT NULL,
    content        TEXT NOT NULL,
    start_char     INTEGER,
    end_char       INTEGER,
    content_hash   TEXT,
    embedding      BLOB,
    model_id       TEXT NOT NULL,
    model_revision TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_owner ON cases(owner_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc  ON chunks(doc_id);
"""


def connect(path: str | Path, *, timeout: float = 5.0) -> sqlite3.Connection:
    """Open a connection with foreign keys on; raise a readable error if the file cannot be used."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"database file not found: {p}")
    if p.stat().st_size == 0:
        raise ValueError(f"database file is empty: {p}")
    con = sqlite3.connect(str(p), timeout=timeout)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    with con:
        con.executescript(SCHEMA)
    return con


def connect_for_write(path: str | Path, *, timeout: float = 5.0) -> sqlite3.Connection:
    """Same as `connect`, but explicit transaction control for rollback tests."""
    con = sqlite3.connect(str(path), timeout=timeout, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_users(con: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
    INSERT INTO users (user_id, role, tenant, display_name, synthetic)
    VALUES (:user_id, :role, :tenant, :display_name, 1)
    ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, tenant=excluded.tenant,
                                       display_name=excluded.display_name
    """
    con.executemany(sql, rows)
    return con.execute("SELECT count(*) FROM users").fetchone()[0]


def upsert_cases(con: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
    INSERT INTO cases (case_id, owner_id, topic, summary, synthetic, created_at)
    VALUES (:case_id, :owner_id, :topic, :summary, 1, :created_at)
    ON CONFLICT(case_id) DO UPDATE SET owner_id=excluded.owner_id, topic=excluded.topic,
                                       summary=excluded.summary, created_at=excluded.created_at
    """
    con.executemany(sql, rows)
    return con.execute("SELECT count(*) FROM cases").fetchone()[0]


def upsert_document(con: sqlite3.Connection, doc: dict) -> None:
    con.execute(
        """
        INSERT INTO documents (doc_id, version, content_hash, title, path, source_url,
                               access, tenant, license, source_type)
        VALUES (:doc_id, :version, :content_hash, :title, :path, :source_url,
                :access, :tenant, :license, :source_type)
        ON CONFLICT(doc_id) DO UPDATE SET version=excluded.version, content_hash=excluded.content_hash,
                                          title=excluded.title, path=excluded.path,
                                          source_url=excluded.source_url, access=excluded.access,
                                          tenant=excluded.tenant, license=excluded.license,
                                          source_type=excluded.source_type
        """,
        doc,
    )


def upsert_chunk(con: sqlite3.Connection, chunk: dict) -> None:
    con.execute(
        """
        INSERT INTO chunks (chunk_id, doc_id, chunk_index, content, start_char, end_char,
                            content_hash, embedding, model_id, model_revision)
        VALUES (:chunk_id, :doc_id, :chunk_index, :content, :start_char, :end_char,
                :content_hash, :embedding, :model_id, :model_revision)
        ON CONFLICT(chunk_id) DO UPDATE SET content=excluded.content,
                                            start_char=excluded.start_char, end_char=excluded.end_char,
                                            content_hash=excluded.content_hash,
                                            embedding=excluded.embedding,
                                            model_id=excluded.model_id,
                                            model_revision=excluded.model_revision
        """,
        chunk,
    )
