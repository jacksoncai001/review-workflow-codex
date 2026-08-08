"""Stable source identity and rebuildable SQLite FTS evidence corpus."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from pydantic import Field

from review_workflow.domain.models import StrictModel


class SourceRecord(StrictModel):
    schema_version: int = 1
    source_id: str
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_path: Path
    size_bytes: int = Field(ge=0)
    extension: str
    title: str | None = None
    doi: str | None = None


class CorpusChunk(StrictModel):
    schema_version: int = 1
    chunk_id: str
    source_id: str
    extraction_id: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    text: str = Field(min_length=1)


class SearchHit(StrictModel):
    chunk_id: str
    source_id: str
    extraction_id: str
    page: int | None
    section: str | None
    text: str
    score: float


def compute_source_id(source_hash: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
        raise ValueError("source_hash must be a lowercase SHA-256 digest")
    return f"src-{source_hash}"


class CorpusStore:
    """Canonical source/chunk store with a derived FTS5 search table."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve(strict=False)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def ingest(self, source: SourceRecord, chunks: list[CorpusChunk]) -> None:
        for chunk in chunks:
            if chunk.source_id != source.source_id:
                raise ValueError(f"Chunk {chunk.chunk_id} belongs to another source")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sources
                    (source_id, source_hash, original_path, size_bytes, extension, title, doi)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    source.source_hash,
                    str(source.original_path),
                    source.size_bytes,
                    source.extension,
                    source.title,
                    source.doi,
                ),
            )
            for chunk in chunks:
                connection.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,))
                connection.execute(
                    """
                    INSERT INTO chunks
                        (chunk_id, source_id, extraction_id, page, section, text)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        source_id=excluded.source_id,
                        extraction_id=excluded.extraction_id,
                        page=excluded.page,
                        section=excluded.section,
                        text=excluded.text
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source_id,
                        chunk.extraction_id,
                        chunk.page,
                        chunk.section,
                        chunk.text,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO chunks_fts
                        (chunk_id, source_id, extraction_id, page, section, text)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source_id,
                        chunk.extraction_id,
                        chunk.page,
                        chunk.section,
                        chunk.text,
                    ),
                )

    def search(self, query: str, top_k: int = 20) -> list[SearchHit]:
        tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
        if not tokens:
            return []
        fts_query = " ".join(f'"{token}"' for token in tokens)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, source_id, extraction_id, page, section, text,
                       bm25(chunks_fts) AS score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts_query, top_k),
            ).fetchall()
        return [
            SearchHit(
                chunk_id=row[0],
                source_id=row[1],
                extraction_id=row[2],
                page=row[3],
                section=row[4],
                text=row[5],
                score=row[6],
            )
            for row in rows
        ]

    def rebuild_index(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chunks_fts")
            connection.execute(
                """
                INSERT INTO chunks_fts (chunk_id, source_id, extraction_id, page, section, text)
                SELECT chunk_id, source_id, extraction_id, page, section, text FROM chunks
                ORDER BY chunk_id
                """
            )

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            sources = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            chunks = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"sources": sources, "chunks": chunks}

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL UNIQUE,
                    original_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    extension TEXT NOT NULL,
                    title TEXT,
                    doi TEXT
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(source_id),
                    extraction_id TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    text TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    source_id UNINDEXED,
                    extraction_id UNINDEXED,
                    page UNINDEXED,
                    section UNINDEXED,
                    text
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
