"""SQLite storage backend for authoritative Idea Inbox records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from importlib import resources
from pathlib import Path

from idea_inbox.config import AppConfig
from idea_inbox.core.models import Idea, IdeaDraft, RawEvent

MIGRATION_PACKAGE = "idea_inbox.storage.migrations"


class SQLiteMigrationError(RuntimeError):
    """Raised when SQLite migrations cannot be applied safely."""


def _connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def open_sqlite_database(config: AppConfig) -> Iterator[sqlite3.Connection]:
    """Open the configured SQLite database with app-wide connection defaults."""
    if config.database_path != Path(":memory:"):
        config.database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = _connect(config.database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _has_fts5(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute("CREATE VIRTUAL TABLE temp.__idea_inbox_fts5_check USING fts5(value)")
    except sqlite3.OperationalError:
        return False
    finally:
        connection.execute("DROP TABLE IF EXISTS temp.__idea_inbox_fts5_check")
    return True


def _tags_to_storage(tags: tuple[str, ...]) -> str:
    normalized_tags = (tag.strip().lower() for tag in tags)
    return " ".join(dict.fromkeys(tag for tag in normalized_tags if tag))


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


def _idea_draft_from_row(row: sqlite3.Row) -> IdeaDraft:
    return IdeaDraft(
        id=row["id"],
        raw_event_id=row["raw_event_id"],
        text=row["text"],
        source_created_at=row["source_created_at"],
        source_uri=row["source_uri"],
        metadata=json.loads(row["metadata"]),
        extraction_state=row["extraction_state"],
    )


def _idea_from_row(row: sqlite3.Row) -> Idea:
    return Idea(
        id=row["id"],
        raw_event_id=row["raw_event_id"],
        draft_id=row["draft_id"],
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

    def __init__(self, database_path: str | Path | AppConfig) -> None:
        if isinstance(database_path, AppConfig):
            database_path = database_path.database_path
        self.database_path = Path(database_path)
        if self.database_path != Path(":memory:"):
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
            "(version TEXT PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, "
            "applied_at TEXT NOT NULL)"
        )
        for migration in sorted(
            resources.files(MIGRATION_PACKAGE).iterdir(), key=lambda path: path.name
        ):
            if not migration.name.endswith(".sql"):
                continue
            stem = migration.name.removesuffix(".sql")
            version, _, name = stem.partition("_")
            sql = migration.read_text(encoding="utf-8")
            checksum = f"sha256:{sha256(sql.encode('utf-8')).hexdigest()}"
            if self._migration_applied(version, name, checksum):
                continue
            if "fts" in name and not _has_fts5(self._connection):
                raise SQLiteMigrationError(
                    "SQLite FTS5 is not available in this Python sqlite3 build; "
                    "install a Python/SQLite build with FTS5 enabled before "
                    "applying search migrations."
                )
            try:
                with self._connection:
                    self._connection.executescript(sql)
                    self._connection.execute(
                        "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                        "VALUES (?, ?, ?, datetime('now'))",
                        (version, name, checksum),
                    )
            except sqlite3.Error as exc:
                raise SQLiteMigrationError(f"Failed to apply migration {stem}: {exc}") from exc

    def _migration_applied(self, version: str, name: str, checksum: str) -> bool:
        row = self._connection.execute(
            "SELECT name, checksum FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row is None:
            return False
        if row["name"] != name or row["checksum"] != checksum:
            raise SQLiteMigrationError(
                f"Migration {version} was already applied with different metadata; "
                "refusing to continue."
            )
        return True

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

    def list_raw_events(
        self, *, processing_state: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[RawEvent]:
        where_clause = ""
        parameters: list[object] = []
        if processing_state is not None:
            where_clause = "WHERE processing_state = ?"
            parameters.append(processing_state)
        parameters.extend([limit, offset])
        rows = self._connection.execute(
            f"""
            SELECT * FROM raw_events
            {where_clause}
            ORDER BY received_at DESC, id ASC
            LIMIT ? OFFSET ?
            """,
            tuple(parameters),
        ).fetchall()
        return [_raw_event_from_row(row) for row in rows]

    def update_raw_event_processing_state(
        self,
        raw_event_id: str,
        processing_state: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> RawEvent | None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE raw_events
                SET processing_state = ?,
                    error_code = ?,
                    error_message = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (processing_state, error_code, error_message, raw_event_id),
            )
        return self.get_raw_event(raw_event_id)

    def save_idea_draft(self, idea_draft: IdeaDraft) -> IdeaDraft:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO idea_drafts (
                  id, raw_event_id, text, source_created_at, source_uri, metadata, extraction_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  raw_event_id = excluded.raw_event_id,
                  text = excluded.text,
                  source_created_at = excluded.source_created_at,
                  source_uri = excluded.source_uri,
                  metadata = excluded.metadata,
                  extraction_state = excluded.extraction_state,
                  updated_at = datetime('now')
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
        stored = self.get_idea_draft(idea_draft.id)
        if stored is None:
            raise SQLiteMigrationError("idea draft write did not persist a readable record")
        return stored

    def get_idea_draft(self, idea_draft_id: str) -> IdeaDraft | None:
        row = self._connection.execute(
            "SELECT * FROM idea_drafts WHERE id = ?",
            (idea_draft_id,),
        ).fetchone()
        return None if row is None else _idea_draft_from_row(row)

    def list_idea_drafts(
        self, *, raw_event_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[IdeaDraft]:
        where_clause = ""
        parameters: list[object] = []
        if raw_event_id is not None:
            where_clause = "WHERE raw_event_id = ?"
            parameters.append(raw_event_id)
        parameters.extend([limit, offset])
        rows = self._connection.execute(
            f"""
            SELECT * FROM idea_drafts
            {where_clause}
            ORDER BY created_at ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            tuple(parameters),
        ).fetchall()
        return [_idea_draft_from_row(row) for row in rows]

    def save_idea(self, idea: Idea) -> Idea:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ideas (
                  id, raw_event_id, draft_id, text, source, source_ref, captured_at, created_at,
                  updated_at, metadata, tags, embedding_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
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
            self._connection.execute("DELETE FROM idea_tags WHERE idea_id = ?", (idea.id,))
            self._connection.executemany(
                "INSERT INTO idea_tags (idea_id, tag) VALUES (?, ?)",
                [(idea.id, tag) for tag in _tags_from_storage(_tags_to_storage(idea.tags))],
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

    def list_ideas(
        self, *, raw_event_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Idea]:
        raw_event_filter = ""
        parameters: list[object] = []
        if raw_event_id is not None:
            raw_event_filter = "AND raw_event_id = ?"
            parameters.append(raw_event_id)
        parameters.extend([limit, offset])
        rows = self._connection.execute(
            f"""
            SELECT * FROM ideas
            WHERE deleted_at IS NULL
            {raw_event_filter}
            ORDER BY captured_at DESC, id ASC
            LIMIT ? OFFSET ?
            """,
            tuple(parameters),
        ).fetchall()
        return [_idea_from_row(row) for row in rows]

    def delete_idea(self, idea_id: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE ideas "
                "SET deleted_at = datetime('now'), updated_at = datetime('now') "
                "WHERE id = ?",
                (idea_id,),
            )

    def clear_fts_projection_for_test(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM idea_fts")
