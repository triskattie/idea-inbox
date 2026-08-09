"""Reusable SQLite connection bootstrap for Idea Inbox storage callers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from idea_inbox.config import AppConfig


@contextmanager
def open_sqlite_database(config: AppConfig) -> Iterator[sqlite3.Connection]:
    """Open the configured SQLite database with app-wide connection defaults."""
    if config.database_path != Path(":memory:"):
        config.database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(config.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
