from pathlib import Path

import pytest

from idea_inbox.config import ConfigError, load_config


def test_load_config_defaults_to_local_sqlite_database_under_project_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IDEA_INBOX_DATABASE_URL", raising=False)
    monkeypatch.delenv("IDEA_INBOX_SQLITE_PATH", raising=False)

    config = load_config(project_root=tmp_path)

    assert config.environment == "development"
    assert config.database_url == "sqlite:///./data/idea-inbox.sqlite3"
    assert config.database_path == tmp_path / "data" / "idea-inbox.sqlite3"


def test_load_config_accepts_configured_sqlite_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_INBOX_DATABASE_URL", "sqlite:///./custom/inbox.sqlite3")
    monkeypatch.delenv("IDEA_INBOX_SQLITE_PATH", raising=False)

    config = load_config(project_root=tmp_path)

    assert config.database_url == "sqlite:///./custom/inbox.sqlite3"
    assert config.database_path == tmp_path / "custom" / "inbox.sqlite3"


def test_load_config_accepts_sqlalchemy_style_async_sqlite_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_INBOX_DATABASE_URL", "sqlite+aiosqlite:///./data/ideas.sqlite3")
    monkeypatch.delenv("IDEA_INBOX_SQLITE_PATH", raising=False)

    config = load_config(project_root=tmp_path)

    assert config.database_url == "sqlite+aiosqlite:///./data/ideas.sqlite3"
    assert config.database_path == tmp_path / "data" / "ideas.sqlite3"


def test_load_config_accepts_configured_sqlite_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured_path = tmp_path / "state" / "ideas.sqlite3"
    monkeypatch.setenv("IDEA_INBOX_SQLITE_PATH", str(configured_path))
    monkeypatch.delenv("IDEA_INBOX_DATABASE_URL", raising=False)

    config = load_config(project_root=tmp_path)

    assert config.database_url == f"sqlite:///{configured_path}"
    assert config.database_path == configured_path


def test_load_config_accepts_postgres_backend_as_optional_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_INBOX_DATABASE_URL", "postgresql://localhost:5432/idea_inbox")
    monkeypatch.delenv("IDEA_INBOX_SQLITE_PATH", raising=False)

    config = load_config(project_root=tmp_path)

    assert config.is_postgres is True
    assert config.database_dsn == "postgresql://localhost:5432/idea_inbox"


def test_load_config_rejects_conflicting_database_location_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_INBOX_DATABASE_URL", "sqlite:///./one.sqlite3")
    monkeypatch.setenv("IDEA_INBOX_SQLITE_PATH", str(tmp_path / "two.sqlite3"))

    with pytest.raises(ConfigError, match="Set only one of"):
        load_config(project_root=tmp_path)
