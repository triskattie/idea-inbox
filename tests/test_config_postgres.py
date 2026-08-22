"""Tests for postgres-aware configuration loading (Phase 9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from idea_inbox.config import DATABASE_URL_ENV, SQLITE_PATH_ENV, ConfigError, load_config


def test_postgres_url_is_accepted_and_flagged_as_postgres() -> None:
    config = load_config(
        {DATABASE_URL_ENV: "postgresql://idea:secret@db.internal:5432/idea_inbox"},
        project_root=Path("/tmp"),
    )

    assert config.is_postgres is True
    assert config.database_dsn == "postgresql://idea:secret@db.internal:5432/idea_inbox"
    assert config.database_path == Path(":memory:")


def test_postgres_scheme_aliases_are_normalized() -> None:
    for url in (
        "postgres://idea@db:5432/idea_inbox",
        "postgresql://idea@db:5432/idea_inbox",
        "postgresql+psycopg://idea@db:5432/idea_inbox",
    ):
        config = load_config({DATABASE_URL_ENV: url}, project_root=Path("/tmp"))

        assert config.is_postgres is True
        assert config.database_dsn.startswith("postgresql://")


def test_sqlite_config_remains_default_and_not_postgres() -> None:
    config = load_config(
        {SQLITE_PATH_ENV: "/tmp/ideas.sqlite3"},
        project_root=Path("/tmp"),
    )

    assert config.is_postgres is False
    assert config.database_dsn == "sqlite:////tmp/ideas.sqlite3"
    assert config.database_path == Path("/tmp/ideas.sqlite3")


def test_postgres_url_with_sqlite_path_conflicts() -> None:
    with pytest.raises(ConfigError):
        load_config(
            {
                DATABASE_URL_ENV: "postgresql://idea@db:5432/idea_inbox",
                SQLITE_PATH_ENV: "/tmp/ideas.sqlite3",
            },
            project_root=Path("/tmp"),
        )


def test_postgres_url_requires_components() -> None:
    with pytest.raises(ConfigError):
        load_config({DATABASE_URL_ENV: "postgresql://"}, project_root=Path("/tmp"))
