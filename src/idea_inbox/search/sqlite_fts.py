"""SQLite FTS5 search index over persisted ideas."""

from __future__ import annotations

import html
import re
import sqlite3
from typing import Any

from idea_inbox.core.models import EmptySearchQuery, Idea, SearchHit, SearchLimitError
from idea_inbox.storage.sqlite import SQLiteStorageBackend

DEFAULT_LIMIT = 10
MAX_LIMIT = 50
_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)
_SNIPPET_START = "\ue000"
_SNIPPET_END = "\ue001"


def _html_safe_snippet(snippet: str) -> str:
    escaped = html.escape(snippet, quote=False)
    return escaped.replace(_SNIPPET_START, "<mark>").replace(_SNIPPET_END, "</mark>")


def _normalize_query(query: str) -> str:
    tokens = _TOKEN_PATTERN.findall(query)
    if not tokens:
        raise EmptySearchQuery("search query must not be empty")
    return " ".join(f'"{token}"' for token in tokens)


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_LIMIT:
        raise SearchLimitError(f"search limit must be between 1 and {MAX_LIMIT}")
    return limit


class SQLiteFTSSearchIndex:
    """SQLite FTS5 implementation of the derived search projection."""

    def __init__(self, storage: SQLiteStorageBackend) -> None:
        self._storage = storage

    @property
    def connection(self) -> sqlite3.Connection:
        return self._storage.connection

    def upsert_idea(self, idea: Idea) -> None:
        existing = self._storage.get_idea(idea.id)
        if existing is None or existing != idea:
            self._storage.save_idea(idea)

    def delete_idea(self, idea_id: str) -> None:
        self._storage.delete_idea(idea_id)

    def rebuild(self) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO idea_fts(idea_fts) VALUES ('rebuild')")

    def search(
        self, query: str, limit: int = DEFAULT_LIMIT, filters: dict[str, Any] | None = None
    ) -> list[SearchHit]:
        normalized_query = _normalize_query(query)
        normalized_limit = _validate_limit(limit)
        filters = filters or {}
        where_clauses = ["idea_fts MATCH ?", "ideas.deleted_at IS NULL"]
        parameters: list[Any] = [_SNIPPET_START, _SNIPPET_END, normalized_query]

        source = filters.get("source")
        if source is not None:
            where_clauses.append("ideas.source = ?")
            parameters.append(source)

        parameters.append(normalized_limit)
        rows = self.connection.execute(
            f"""
            SELECT
              ideas.id AS idea_id,
              ideas.text AS text,
              bm25(idea_fts) AS score,
              ideas.source AS source,
              ideas.captured_at AS captured_at,
              snippet(idea_fts, 0, ?, ?, '…', 32) AS snippet
            FROM idea_fts
            JOIN ideas ON ideas.rowid = idea_fts.rowid
            WHERE {" AND ".join(where_clauses)}
            ORDER BY score ASC, ideas.captured_at DESC, ideas.id ASC
            LIMIT ?
            """,
            tuple(parameters),
        ).fetchall()
        return [
            SearchHit(
                idea_id=row["idea_id"],
                text=row["text"],
                score=float(row["score"]),
                rank=index,
                source=row["source"],
                captured_at=row["captured_at"],
                snippet=_html_safe_snippet(row["snippet"]),
            )
            for index, row in enumerate(rows, start=1)
        ]
