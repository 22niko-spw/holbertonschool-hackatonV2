# Implémentations persistantes (SQLite) de CorpusStore / ReportStore — Kévin
# Interfaces définies par Yo dans rene_la_taupe.tools.

from __future__ import annotations

import re
import sqlite3
import threading
from datetime import UTC, datetime

from rene_la_taupe.schemas import CitedAnswer, DocHit, DocMeta, QuarantineEntry, Report
from rene_la_taupe.tools import CorpusStore, ReportStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpora (
    corpus_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'ingested',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('clean', 'quarantined')),
    upload_ts TEXT NOT NULL,
    sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    corpus_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    technique TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    confidence REAL NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer_json TEXT NOT NULL,
    quarantine_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_corpus ON documents(corpus_id);
CREATE INDEX IF NOT EXISTS idx_chunks_corpus ON chunks(corpus_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_corpus ON quarantine_entries(corpus_id);
CREATE INDEX IF NOT EXISTS idx_reports_corpus ON reports(corpus_id);
"""

_WORD_RE = re.compile(r"[a-zàâäéèêëïîôöùûüç0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


class SqliteDatabase:
    """Connexion SQLite partagée entre CorpusStore et ReportStore."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        return self._local.conn  # type: ignore[no-any-return]

    def connection(self) -> sqlite3.Connection:
        return self._connect()


class SqliteCorpusStore(CorpusStore):
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def create_corpus(self, corpus_id: str) -> None:
        conn = self._db.connection()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO corpora (corpus_id, status, created_at) VALUES (?, 'ingested', ?)",
                (corpus_id, datetime.now(UTC).isoformat()),
            )

    def add_document(
        self,
        corpus_id: str,
        doc_id: str,
        filename: str,
        status: str,
        sha256: str,
        chunks: list[str],
    ) -> None:
        conn = self._db.connection()
        with conn:
            conn.execute(
                """INSERT INTO documents (doc_id, corpus_id, filename, status, upload_ts, sha256)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (doc_id, corpus_id, filename, status, datetime.now(UTC).isoformat(), sha256),
            )
            conn.executemany(
                "INSERT INTO chunks (chunk_id, doc_id, corpus_id, idx, text) VALUES (?, ?, ?, ?, ?)",
                [
                    (f"{doc_id}-c{i}", doc_id, corpus_id, i, chunk_text)
                    for i, chunk_text in enumerate(chunks)
                ],
            )

    def add_quarantine_entries(self, corpus_id: str, entries: list[QuarantineEntry]) -> None:
        if not entries:
            return
        conn = self._db.connection()
        with conn:
            conn.executemany(
                """INSERT INTO quarantine_entries
                   (corpus_id, doc_id, technique, excerpt, confidence, detected_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (corpus_id, e.doc_id, e.technique, e.excerpt, e.confidence, e.detected_at)
                    for e in entries
                ],
            )

    def mark_processed(self, corpus_id: str) -> None:
        conn = self._db.connection()
        with conn:
            conn.execute(
                "UPDATE corpora SET status = 'processed' WHERE corpus_id = ?", (corpus_id,)
            )

    def corpus_exists(self, corpus_id: str) -> bool:
        conn = self._db.connection()
        row = conn.execute(
            "SELECT 1 FROM corpora WHERE corpus_id = ?", (corpus_id,)
        ).fetchone()
        return row is not None

    def list_documents(self, corpus_id: str) -> list[DocMeta]:
        conn = self._db.connection()
        rows = conn.execute(
            "SELECT doc_id, filename, status, upload_ts, sha256 FROM documents WHERE corpus_id = ?",
            (corpus_id,),
        ).fetchall()
        return [DocMeta(**dict(row)) for row in rows]

    # ─── CorpusStore interface ───

    def search(self, corpus_id: str, query: str, k: int) -> list[DocHit]:
        conn = self._db.connection()
        rows = conn.execute(
            """SELECT c.chunk_id, c.doc_id, c.text
               FROM chunks c
               JOIN documents d ON d.doc_id = c.doc_id
               WHERE c.corpus_id = ? AND d.status = 'clean'""",
            (corpus_id,),
        ).fetchall()

        query_words = set(_tokenize(query))
        if not query_words:
            return []

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            chunk_words = _tokenize(row["text"])
            if not chunk_words:
                continue
            overlap = query_words.intersection(chunk_words)
            if not overlap:
                continue
            score = len(overlap) / len(query_words)
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            DocHit(doc_id=row["doc_id"], chunk_id=row["chunk_id"], score=score, text=row["text"])
            for score, row in scored[:k]
        ]

    def get_metadata(self, doc_id: str) -> DocMeta | None:
        conn = self._db.connection()
        row = conn.execute(
            "SELECT doc_id, filename, status, upload_ts, sha256 FROM documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        return DocMeta(**dict(row)) if row else None

    def list_quarantine(self, corpus_id: str) -> list[QuarantineEntry]:
        conn = self._db.connection()
        rows = conn.execute(
            """SELECT doc_id, technique, excerpt, confidence, detected_at
               FROM quarantine_entries WHERE corpus_id = ?
               ORDER BY detected_at""",
            (corpus_id,),
        ).fetchall()
        return [QuarantineEntry(**dict(row)) for row in rows]

    def get_quarantine_excerpt(self, doc_id: str, chunk_id: str) -> str | None:
        conn = self._db.connection()
        row = conn.execute(
            """SELECT c.text FROM chunks c
               JOIN documents d ON d.doc_id = c.doc_id
               WHERE c.doc_id = ? AND c.chunk_id = ? AND d.status = 'quarantined'""",
            (doc_id, chunk_id),
        ).fetchone()
        return row["text"] if row else None


class SqliteReportStore(ReportStore):
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def save_report(self, report: Report) -> Report:
        conn = self._db.connection()
        with conn:
            conn.execute(
                """INSERT INTO reports (report_id, corpus_id, question, answer_json, quarantine_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    report.report_id,
                    report.corpus_id,
                    report.question,
                    report.answer.model_dump_json(),
                    _quarantine_to_json(report.quarantine),
                    report.created_at,
                ),
            )
        return report

    def get_report(self, report_id: str) -> Report | None:
        conn = self._db.connection()
        row = conn.execute(
            "SELECT * FROM reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        if not row:
            return None
        return Report(
            report_id=row["report_id"],
            corpus_id=row["corpus_id"],
            question=row["question"],
            answer=CitedAnswer.model_validate_json(row["answer_json"]),
            quarantine=_quarantine_from_json(row["quarantine_json"]),
            created_at=row["created_at"],
        )


def _quarantine_to_json(entries: list[QuarantineEntry]) -> str:
    import json

    return json.dumps([e.model_dump() for e in entries])


def _quarantine_from_json(raw: str) -> list[QuarantineEntry]:
    import json

    return [QuarantineEntry(**item) for item in json.loads(raw)]
