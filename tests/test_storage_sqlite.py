from pathlib import Path

from idea_inbox.config import AppConfig
from idea_inbox.storage.sqlite import open_sqlite_database


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
