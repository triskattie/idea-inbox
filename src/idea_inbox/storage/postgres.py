"""Optional Postgres (pgvector image) storage backend for Idea Inbox.

Requires the `postgres` optional dependency group (`pip install -e '.[postgres]'`).
`psycopg` is imported lazily so the base install never needs it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from idea_inbox.config import AppConfig
from idea_inbox.core.models import Idea, IdeaDraft, RawEvent

MIGRATION_PACKAGE = "idea_inbox.storage.postgres_migrations"

_POSTGRES_MIGRATIONS: tuple[str, ...] = ("0001_postgres_foundation",)


class PostgresStorageError(RuntimeError):
    """Raised when Postgres storage operations cannot be completed safely."""


def _require_psycopg() -> Any:
    try:
        import psycopg  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised via opt-in group only
        raise PostgresStorageError(
            "psycopg is required for the Postgres profile; "
            "install it with `pip install -e '.[postgres]'`."
        ) from exc
    return psycopg


def _tags_to_storage(tags: tuple[str, ...]) -> str:
    normalized_tags = (tag.strip().lower() for tag in tags)
    return " ".join(dict.fromkeys(tag for tag in normalized_tags if tag))


def _tags_from_storage(tags: str) -> tuple[str, ...]:
    return tuple(tag for tag in tags.split(" ") if tag)


def _raw_event_from_row(row: dict[str, Any]) -> RawEvent:
    return RawEvent(
        id=row["id"],
        source=row["source"],
        provider_event_id=row["provider_event_id"],
        dedupe_key=row["dedupe_key"],
        received_at=str(row["received_at"]),
        occurred_at=_timestamp_to_iso(row["occurred_at"]),
        actor_ref=row["actor_ref"],
        payload=row["payload"],
        payload_hash=row["payload_hash"],
        processing_state=row["processing_state"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def _idea_draft_from_row(row: dict[str, Any]) -> IdeaDraft:
    return IdeaDraft(
        id=row["id"],
        raw_event_id=row["raw_event_id"],
        text=row["text"],
        source_created_at=_timestamp_to_iso(row["source_created_at"]),
        source_uri=row["source_uri"],
        metadata=json.loads(row["metadata"])
        if isinstance(row["metadata"], str)
        else row["metadata"],
        extraction_state=row["extraction_state"],
    )


def _idea_from_row(row: dict[str, Any]) -> Idea:
    metadata = row["metadata"]
    return Idea(
        id=row["id"],
        raw_event_id=row["raw_event_id"],
        draft_id=row["draft_id"],
        text=row["text"],
        source=row["source"],
        source_ref=row["source_ref"],
        captured_at=_timestamp_to_iso(row["captured_at"]),
        created_at=_timestamp_to_iso(row["created_at"]),
        updated_at=_timestamp_to_iso(row["updated_at"]),
        metadata=json.loads(metadata) if isinstance(metadata, str) else metadata,
        tags=_tags_from_storage(row["tags"]),
        embedding_state=row["embedding_state"],
    )


def _timestamp_to_iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


class PostgresStorageBackend:
    """Postgres implementation of the authoritative storage boundary.

    Satisfies the same service contracts as SQLiteStorageBackend so services,
    routes, and search adapters do not change between backends.
    """

    def __init__(self, dsn: str | AppConfig) -> None:
        psycopg = _require_psycopg()
        self._dsn = dsn.database_dsn if isinstance(dsn, AppConfig) else dsn
        self._connection = psycopg.connect(self._dsn)

    @property
    def connection(self) -> Any:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._connection.transaction():
            yield

    def migrate(self) -> None:
        """Apply deterministic repository migrations idempotently."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  checksum TEXT NOT NULL,
                  applied_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                )
                """
            )
            self._connection.commit()
            for stem in _POSTGRES_MIGRATIONS:
                version, _, name = stem.partition("_")
                sql = _migration_sql(stem)
                checksum = f"sha256:{_checksum(sql)}"
                cursor.execute(
                    "SELECT name, checksum FROM schema_migrations WHERE version = %s", (version,)
                )
                applied = cursor.fetchone()
                if applied is not None:
                    if applied[0] != name or applied[1] != checksum:
                        raise PostgresStorageError(
                            f"Migration {version} was already applied with different metadata; "
                            "refusing to continue."
                        )
                    continue
                cursor.execute(sql)
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                    (version, name, checksum),
                )
            self._connection.commit()

    # -- raw events ---------------------------------------------------------

    def save_raw_event(self, raw_event: RawEvent) -> RawEvent:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO raw_events (
                  id, source, provider_event_id, dedupe_key, received_at, occurred_at,
                  actor_ref, payload, payload_hash, processing_state, error_code, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source, dedupe_key) DO NOTHING
                """,
                (
                    raw_event.id,
                    raw_event.source,
                    raw_event.provider_event_id,
                    raw_event.dedupe_key,
                    raw_event.received_at,
                    raw_event.occurred_at,
                    raw_event.actor_ref,
                    raw_event.payload,
                    raw_event.payload_hash,
                    raw_event.processing_state,
                    raw_event.error_code,
                    raw_event.error_message,
                ),
            )
            self._connection.commit()
        existing = self._fetchone(
            "SELECT * FROM raw_events WHERE source = %s AND dedupe_key = %s",
            (raw_event.source, raw_event.dedupe_key),
        )
        if existing is None:
            raise PostgresStorageError("raw event write did not persist a readable record")
        return _raw_event_from_row(existing)

    def get_raw_event(self, raw_event_id: str) -> RawEvent | None:
        row = self._fetchone("SELECT * FROM raw_events WHERE id = %s", (raw_event_id,))
        return None if row is None else _raw_event_from_row(row)

    def count_raw_events(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS total FROM raw_events")
        return int(row["total"])

    def list_raw_events(
        self, *, processing_state: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[RawEvent]:
        where_clause = ""
        parameters: list[object] = []
        if processing_state is not None:
            where_clause = "WHERE processing_state = %s"
            parameters.append(processing_state)
        parameters.extend([limit, offset])
        rows = self._fetchall(
            f"""
            SELECT * FROM raw_events
            {where_clause}
            ORDER BY received_at DESC, id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(parameters),
        )
        return [_raw_event_from_row(row) for row in rows]

    def update_raw_event_processing_state(
        self,
        raw_event_id: str,
        processing_state: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> RawEvent | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE raw_events
                SET processing_state = %s,
                    error_code = %s,
                    error_message = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (processing_state, error_code, error_message, raw_event_id),
            )
            self._connection.commit()
        return self.get_raw_event(raw_event_id)

    # -- idea drafts --------------------------------------------------------

    def save_idea_draft(self, idea_draft: IdeaDraft) -> IdeaDraft:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO idea_drafts (
                  id, raw_event_id, text, source_created_at, source_uri, metadata,
                  extraction_state
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  raw_event_id = excluded.raw_event_id,
                  text = excluded.text,
                  source_created_at = excluded.source_created_at,
                  source_uri = excluded.source_uri,
                  metadata = excluded.metadata,
                  extraction_state = excluded.extraction_state,
                  updated_at = now()
                """,
                (
                    idea_draft.id,
                    idea_draft.raw_event_id,
                    idea_draft.text,
                    idea_draft.source_created_at,
                    idea_draft.source_uri,
                    json.dumps(idea_draft.metadata, sort_keys=True),
                    idea_draft.extraction_state,
                ),
            )
            self._connection.commit()
        stored = self.get_idea_draft(idea_draft.id)
        if stored is None:
            raise PostgresStorageError("idea draft write did not persist a readable record")
        return stored

    def get_idea_draft(self, idea_draft_id: str) -> IdeaDraft | None:
        row = self._fetchone("SELECT * FROM idea_drafts WHERE id = %s", (idea_draft_id,))
        return None if row is None else _idea_draft_from_row(row)

    def list_idea_drafts(
        self, *, raw_event_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[IdeaDraft]:
        where_clause = ""
        parameters: list[object] = []
        if raw_event_id is not None:
            where_clause = "WHERE raw_event_id = %s"
            parameters.append(raw_event_id)
        parameters.extend([limit, offset])
        rows = self._fetchall(
            f"""
            SELECT * FROM idea_drafts
            {where_clause}
            ORDER BY created_at ASC, id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(parameters),
        )
        return [_idea_draft_from_row(row) for row in rows]

    # -- ideas --------------------------------------------------------------

    def save_idea(self, idea: Idea) -> Idea:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ideas (
                  id, raw_event_id, draft_id, text, source, source_ref, captured_at, created_at,
                  updated_at, metadata, tags, embedding_state
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  raw_event_id = excluded.raw_event_id,
                  draft_id = excluded.draft_id,
                  text = excluded.text,
                  source = excluded.source,
                  source_ref = excluded.source_ref,
                  captured_at = excluded.captured_at,
                  created_at = excluded.created_at,
                  updated_at = excluded.updated_at,
                  metadata = excluded.metadata,
                  tags = excluded.tags,
                  embedding_state = excluded.embedding_state
                """,
                (
                    idea.id,
                    idea.raw_event_id,
                    idea.draft_id,
                    idea.text,
                    idea.source,
                    idea.source_ref,
                    idea.captured_at,
                    idea.created_at,
                    idea.updated_at,
                    json.dumps(idea.metadata, sort_keys=True),
                    _tags_to_storage(idea.tags),
                    idea.embedding_state,
                ),
            )
            cursor.execute("DELETE FROM idea_tags WHERE idea_id = %s", (idea.id,))
            cursor.executemany(
                "INSERT INTO idea_tags (idea_id, tag) VALUES (%s, %s)",
                [(idea.id, tag) for tag in _tags_from_storage(_tags_to_storage(idea.tags))],
            )
            self._connection.commit()
        stored = self.get_idea(idea.id)
        if stored is None:
            raise PostgresStorageError("idea write did not persist a readable record")
        return stored

    def get_idea(self, idea_id: str) -> Idea | None:
        row = self._fetchone("SELECT * FROM ideas WHERE id = %s AND deleted_at IS NULL", (idea_id,))
        return None if row is None else _idea_from_row(row)

    def list_ideas(
        self, *, raw_event_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Idea]:
        raw_event_filter = ""
        parameters: list[object] = []
        if raw_event_id is not None:
            raw_event_filter = "AND raw_event_id = %s"
            parameters.append(raw_event_id)
        parameters.extend([limit, offset])
        rows = self._fetchall(
            f"""
            SELECT * FROM ideas
            WHERE deleted_at IS NULL
            {raw_event_filter}
            ORDER BY captured_at DESC, id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(parameters),
        )
        return [_idea_from_row(row) for row in rows]

    def delete_idea(self, idea_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ideas
                SET deleted_at = now(), updated_at = now()
                WHERE id = %s
                """,
                (idea_id,),
            )
            self._connection.commit()

    def applied_versions(self) -> list[str]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [str(row[0]) for row in cursor.fetchall()]

    def save_idea_from_parts(
        self,
        *,
        idea_id: str,
        draft_id: str,
        text: str,
        captured_at: str,
        source: str = "manual",
        source_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: tuple[str, ...] = (),
    ) -> None:
        """Persist an idea for an existing draft (integration-test helper)."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.save_idea(
            Idea(
                id=idea_id,
                raw_event_id=self._draft_raw_event(draft_id),
                draft_id=draft_id,
                text=text,
                source=source,
                source_ref=source_ref,
                captured_at=captured_at,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
                tags=tags,
                embedding_state="not_requested",
            )
        )

    def _draft_raw_event(self, draft_id: str) -> str:
        draft = self.get_idea_draft(draft_id)
        if draft is None:
            raise PostgresStorageError(f"unknown draft {draft_id}")
        return draft.raw_event_id

    # -- helpers ------------------------------------------------------------

    def _fetchone(self, sql: str, parameters: tuple[object, ...] = ()) -> dict[str, Any] | None:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, parameters)
            columns = [description.name for description in cursor.description]
            row = cursor.fetchone()
        if row is None:
            return None
        return dict(zip(columns, row, strict=True))

    def _fetchall(self, sql: str, parameters: tuple[object, ...]) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, parameters)
            columns = [description.name for description in cursor.description]
            rows = cursor.fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]


def _checksum(sql: str) -> str:
    from hashlib import sha256

    return sha256(sql.encode("utf-8")).hexdigest()


def _migration_sql(stem: str) -> str:
    path = resources.files(MIGRATION_PACKAGE) / f"{stem}.sql"
    return Path(str(path)).read_text(encoding="utf-8")


__all__ = ["PostgresStorageBackend", "PostgresStorageError"]
