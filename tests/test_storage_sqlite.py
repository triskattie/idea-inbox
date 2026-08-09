from pathlib import Path

from idea_inbox.config import AppConfig
from idea_inbox.storage.sqlite import SQLiteStorageBackend, open_sqlite_database


def table_columns(storage: SQLiteStorageBackend, table_name: str) -> set[str]:
    rows = storage.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def index_names(storage: SQLiteStorageBackend, table_name: str) -> set[str]:
    rows = storage.connection.execute(f"PRAGMA index_list({table_name})").fetchall()
    return {row["name"] for row in rows}


def foreign_key_targets(storage: SQLiteStorageBackend, table_name: str) -> set[tuple[str, str]]:
    rows = storage.connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return {(row["from"], row["table"]) for row in rows}


def test_open_sqlite_database_creates_parent_directory_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "nested" / "idea-inbox.sqlite3"
    config = AppConfig(
        environment="development",
        log_level="INFO",
        database_url=f"sqlite:///{database_path}",
        database_path=database_path,
    )

    with open_sqlite_database(config) as connection:
        foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()
        connection.execute("CREATE TABLE smoke (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
        connection.execute("INSERT INTO smoke (body) VALUES (?)", ("ok",))
        stored_body = connection.execute("SELECT body FROM smoke").fetchone()

    assert database_path.exists()
    assert foreign_keys_enabled is not None
    assert foreign_keys_enabled[0] == 1
    assert stored_body is not None
    assert stored_body[0] == "ok"


def test_open_sqlite_database_uses_row_access_by_column_name(tmp_path: Path) -> None:
    database_path = tmp_path / "idea-inbox.sqlite3"
    config = AppConfig(
        environment="development",
        log_level="INFO",
        database_url=f"sqlite:///{database_path}",
        database_path=database_path,
    )

    with open_sqlite_database(config) as connection:
        connection.execute("CREATE TABLE smoke (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
        connection.execute("INSERT INTO smoke (body) VALUES (?)", ("ok",))
        row = connection.execute("SELECT id, body FROM smoke").fetchone()

    assert row is not None
    assert row["body"] == "ok"


def test_fresh_sqlite_migration_creates_schema_plan_foundation(tmp_path: Path) -> None:
    storage = SQLiteStorageBackend(tmp_path / "idea-inbox.sqlite3")
    try:
        storage.migrate()

        tables = set(storage.table_names())
        assert {
            "schema_migrations",
            "raw_events",
            "idea_drafts",
            "ideas",
            "idea_tags",
            "idea_fts",
        } <= tables
        assert table_columns(storage, "schema_migrations") == {
            "version",
            "name",
            "checksum",
            "applied_at",
        }
        assert {
            "id",
            "source",
            "provider_event_id",
            "dedupe_key",
            "received_at",
            "occurred_at",
            "actor_ref",
            "payload",
            "payload_hash",
            "processing_state",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
        } <= table_columns(storage, "raw_events")
        assert {
            "id",
            "raw_event_id",
            "text",
            "source_created_at",
            "source_uri",
            "metadata",
            "extraction_state",
            "created_at",
            "updated_at",
        } <= table_columns(storage, "idea_drafts")
        assert {
            "id",
            "raw_event_id",
            "draft_id",
            "text",
            "source",
            "source_ref",
            "captured_at",
            "metadata",
            "embedding_state",
            "created_at",
            "updated_at",
            "deleted_at",
        } <= table_columns(storage, "ideas")
        assert table_columns(storage, "idea_tags") == {"idea_id", "tag", "created_at"}
        assert ("raw_event_id", "raw_events") in foreign_key_targets(storage, "idea_drafts")
        assert ("raw_event_id", "raw_events") in foreign_key_targets(storage, "ideas")
        assert ("draft_id", "idea_drafts") in foreign_key_targets(storage, "ideas")
        assert ("idea_id", "ideas") in foreign_key_targets(storage, "idea_tags")
        assert {
            "idx_raw_events_source_provider_event_id",
            "idx_raw_events_processing_state",
            "idx_raw_events_received_at",
        } <= index_names(storage, "raw_events")
        assert {
            "idx_idea_drafts_raw_event_id",
            "idx_idea_drafts_extraction_state",
        } <= index_names(storage, "idea_drafts")
        assert {
            "idx_ideas_raw_event_id",
            "idx_ideas_draft_id",
            "idx_ideas_source_ref",
            "idx_ideas_captured_at",
            "idx_ideas_embedding_state",
        } <= index_names(storage, "ideas")
        assert "idx_idea_tags_tag" in index_names(storage, "idea_tags")
    finally:
        storage.close()


def test_migration_records_names_checksums_and_reruns_without_duplicates(tmp_path: Path) -> None:
    storage = SQLiteStorageBackend(tmp_path / "idea-inbox.sqlite3")
    try:
        storage.migrate()
        storage.migrate()

        rows = storage.connection.execute(
            "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert [row["version"] for row in rows] == ["0001", "0002"]
        assert [row["name"] for row in rows] == ["initial_storage", "idea_fts"]
        assert all(row["checksum"].startswith("sha256:") for row in rows)
        assert all(row["applied_at"] for row in rows)
    finally:
        storage.close()
