"""SQLite storage backend for authoritative Idea Inbox records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from idea_inbox.core.models import Idea, RawEvent

MIGRATION_PACKAGE = "idea_inbox.storage.migrations"


class SQLiteMigrationError(RuntimeError):
    """Raised when SQLite migrations cannot be applied safely."""


def _connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _has_fts5(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute("CREATE VIRTUAL TABLE temp.__idea_inbox_fts5_check USING fts5(value)")
    except sqlite3.OperationalError:
        return False
    finally:
        connection.execute("DROP TABLE IF EXISTS temp.__idea_inbox_fts5_check")
    return True


def _tags_to_storage(tags: tuple[str, ...]) -> str:
    return " ".join(tag.strip().lower() for tag in tags if tag.strip())


def _tags_from_storage(tags: str) -> tuple[str, ...]:
    return tuple(tag for tag in tags.split(" ") if tag)


def _raw_event_from_row(row: sqlite3.Row) -> RawEvent:
    return RawEvent(
        id=row["id"],
        source=row["source"],
        provider_event_id=row["provider_event_id"],
        dedupe_key=row["dedupe_key"],
        received_at=row["received_at"],
        occurred_at=row["occurred_at"],
        actor_ref=row["actor_ref"],
        payload=row["payload"],
        payload_hash=row["payload_hash"],
        processing_state=row["processing_state"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def _idea_from_row(row: sqlite3.Row) -> Idea:
    return Idea(
        id=row["id"],
        raw_event_id=row["raw_event_id"],
        text=row["text"],
        source=row["source"],
        source_ref=row["source_ref"],
        captured_at=row["captured_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=json.loads(row["metadata"]),
        tags=_tags_from_storage(row["tags"]),
        embedding_state=row["embedding_state"],
    )


class SQLiteStorageBackend:
    """SQLite implementation of the authoritative storage boundary."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = _connect(self.database_path)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._connection:
            yield

    def migrate(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        for migration in sorted(
            resources.files(MIGRATION_PACKAGE).iterdir(), key=lambda path: path.name
        ):
            if not migration.name.endswith(".sql"):
                continue
            version = migration.name.removesuffix(".sql")
            if self._migration_applied(version):
                continue
            if "fts" in version and not _has_fts5(self._connection):
                raise SQLiteMigrationError(
                    "SQLite FTS5 is not available in this Python sqlite3 build; "
                    "install a Python/SQLite build with FTS5 enabled before "
                    "applying search migrations."
                )
            sql = migration.read_text(encoding="utf-8")
            try:
                with self._connection:
                    self._connection.executescript(sql)
                    self._connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) "
                        "VALUES (?, datetime('now'))",
                        (version,),
                    )
            except sqlite3.Error as exc:
                raise SQLiteMigrationError(f"Failed to apply migration {version}: {exc}") from exc

    def _migration_applied(self, version: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        return row is not None

    def applied_migration_versions(self) -> list[str]:
        rows = self._connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        return [row["version"] for row in rows]

    def table_names(self) -> list[str]:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table') ORDER BY name"
        ).fetchall()
        return [row["name"] for row in rows]

    def save_raw_event(self, raw_event: RawEvent) -> RawEvent:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO raw_events (
                  id, source, provider_event_id, dedupe_key, received_at, occurred_at,
                  actor_ref, payload, payload_hash, processing_state, error_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        existing = self._connection.execute(
            "SELECT * FROM raw_events WHERE source = ? AND dedupe_key = ?",
            (raw_event.source, raw_event.dedupe_key),
        ).fetchone()
        if existing is None:
            raise SQLiteMigrationError("raw event write did not persist a readable record")
        return _raw_event_from_row(existing)

    def get_raw_event(self, raw_event_id: str) -> RawEvent | None:
        row = self._connection.execute(
            "SELECT * FROM raw_events WHERE id = ?",
            (raw_event_id,),
        ).fetchone()
        return None if row is None else _raw_event_from_row(row)

    def count_raw_events(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS total FROM raw_events").fetchone()
        return int(row["total"])

    def save_idea(self, idea: Idea) -> Idea:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ideas (
                  id, raw_event_id, text, source, source_ref, captured_at, created_at,
                  updated_at, metadata, tags, embedding_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  raw_event_id = excluded.raw_event_id,
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
        stored = self.get_idea(idea.id)
        if stored is None:
            raise SQLiteMigrationError("idea write did not persist a readable record")
        return stored

    def get_idea(self, idea_id: str) -> Idea | None:
        row = self._connection.execute(
            "SELECT * FROM ideas WHERE id = ?",
            (idea_id,),
        ).fetchone()
        return None if row is None else _idea_from_row(row)

    def delete_idea(self, idea_id: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))

    def clear_fts_projection_for_test(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM idea_fts")
