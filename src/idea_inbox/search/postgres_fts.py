"""Optional Postgres tsvector-backed search index for Idea Inbox.

Implements the same ``SearchIndex`` contract as the SQLite FTS adapter so
services and routes do not change between backends. Requires the ``postgres``
optional dependency group.
"""

from __future__ import annotations

import re
from typing import Any

from idea_inbox.core.models import SearchHit
from idea_inbox.storage.postgres import PostgresStorageBackend

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class EmptySearchQuery(ValueError):
    """Raised when a normalized search query has no searchable tokens."""


class SearchLimitError(ValueError):
    """Raised when a requested search limit is outside the allowed range."""


class PostgresFTSSearchIndex:
    """tsvector-backed search adapter over the shared search contract."""

    def __init__(self, storage: PostgresStorageBackend) -> None:
        self._storage = storage

    def upsert_idea(self, idea_id: str) -> None:  # pragma: no cover - trigger-maintained
        """Projection is maintained by triggers; kept for contract parity."""
        return None

    def delete_idea(self, idea_id: str) -> None:  # pragma: no cover - cascade-maintained
        """Projection rows cascade with their idea; kept for contract parity."""
        return None

    def rebuild(self) -> None:
        upsert_sql = """
                INSERT INTO idea_search (idea_id, document)
                SELECT id, to_tsvector('simple',
                    text || ' ' || tags || ' ' || COALESCE(source_ref, ''))
                FROM ideas
                ON CONFLICT (idea_id) DO UPDATE SET document = EXCLUDED.document
                """
        with self._storage.connection.cursor() as cursor:
            cursor.execute(upsert_sql)
            self._storage.connection.commit()

    def search(
        self, query: str, limit: int = DEFAULT_LIMIT, filters: dict[str, Any] | None = None
    ) -> list[SearchHit]:
        if not 1 <= limit <= MAX_LIMIT:
            raise SearchLimitError(f"search limit must be between 1 and {MAX_LIMIT}")
        tsquery = _normalized_tsquery(query)
        if not tsquery:
            raise EmptySearchQuery("search query must not be empty")
        filters = filters or {}

        source_filter_sql = ""
        parameters: list[object] = [tsquery]
        source = filters.get("source")
        if source is not None:
            source_filter_sql = "AND ideas.source = %s"
            parameters.append(source)
        parameters.append(limit)

        with self._storage.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                  ideas.id,
                  ideas.text,
                  ideas.source,
                  ideas.source_ref,
                  ideas.captured_at,
                  ts_rank(idea_search.document, query) AS rank_score
                FROM idea_search
                JOIN ideas ON ideas.id = idea_search.idea_id
                CROSS JOIN websearch_to_tsquery('simple', %s) AS query
                WHERE ideas.deleted_at IS NULL AND idea_search.document @@ query
                {source_filter_sql}
                ORDER BY rank_score DESC, ideas.captured_at DESC, ideas.id ASC
                LIMIT %s
                """,
                tuple(parameters),
            )
            columns = [description.name for description in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        return [
            SearchHit(
                idea_id=row["id"],
                text=row["text"],
                score=float(row["rank_score"]),
                rank=index + 1,
                source=row["source"],
                captured_at=str(row["captured_at"]),
                snippet=_snippet(row["text"], query),
            )
            for index, row in enumerate(rows)
        ]


def _normalized_tsquery(query: str) -> str:
    tokens = _TOKEN_PATTERN.findall(query)
    return " ".join(tokens)


def _snippet(text: str, query: str, width: int = 160) -> str:
    tokens = [token.lower() for token in _TOKEN_PATTERN.findall(query)]
    lowered = text.lower()
    best_position = min(
        (lowered.find(token) for token in tokens if token and lowered.find(token) >= 0),
        default=-1,
    )
    if best_position < 0:
        return text[:width].strip()
    start = max(0, best_position - width // 3)
    return text[start : start + width].strip()


__all__ = ["PostgresFTSSearchIndex", "EmptySearchQuery", "SearchLimitError"]
