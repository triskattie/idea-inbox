"""Configuration loading for Idea Inbox."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENVIRONMENT = "development"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_DATABASE_URL = "sqlite:///./data/idea-inbox.sqlite3"

POSTGRES_URL_PREFIXES = ("postgresql://", "postgres://", "postgresql+psycopg://")

DATABASE_URL_ENV = "IDEA_INBOX_DATABASE_URL"
SQLITE_PATH_ENV = "IDEA_INBOX_SQLITE_PATH"
ENVIRONMENT_ENV = "IDEA_INBOX_ENV"
LOG_LEVEL_ENV = "IDEA_INBOX_LOG_LEVEL"


class ConfigError(ValueError):
    """Raised when Idea Inbox configuration is invalid."""


@dataclass(frozen=True)
class AppConfig:
    """Typed application settings shared by CLI, API, and storage callers."""

    environment: str
    log_level: str
    database_url: str
    database_path: Path

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(POSTGRES_URL_PREFIXES)

    @property
    def database_dsn(self) -> str:
        """Normalized connection DSN for the selected backend."""
        if not self.is_postgres:
            return self.database_url
        scheme, _, rest = self.database_url.partition("://")
        return f"postgresql://{rest}" if scheme != "postgresql" else self.database_url


def load_config(
    env: Mapping[str, str] | None = None,
    *,
    project_root: Path | None = None,
) -> AppConfig:
    """Load Idea Inbox settings from environment variables with local-dev defaults."""
    values = os.environ if env is None else env
    root = Path.cwd() if project_root is None else project_root

    database_url = values.get(DATABASE_URL_ENV, "").strip()
    sqlite_path = values.get(SQLITE_PATH_ENV, "").strip()

    if database_url and sqlite_path:
        raise ConfigError(f"Set only one of {DATABASE_URL_ENV} or {SQLITE_PATH_ENV}.")

    if sqlite_path:
        database_path = _resolve_database_path(sqlite_path, root)
        database_url = _database_url_for_path(database_path)
    else:
        database_url = database_url or DEFAULT_DATABASE_URL
        if database_url.startswith(POSTGRES_URL_PREFIXES):
            database_path = Path(":memory:")
            _validate_postgres_dsn(database_url)
        else:
            database_path = _sqlite_path_from_url(database_url, root)

    return AppConfig(
        environment=values.get(ENVIRONMENT_ENV, DEFAULT_ENVIRONMENT).strip() or DEFAULT_ENVIRONMENT,
        log_level=values.get(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL).strip() or DEFAULT_LOG_LEVEL,
        database_url=database_url,
        database_path=database_path,
    )


def _validate_postgres_dsn(database_url: str) -> None:
    from urllib.parse import urlsplit

    parts = urlsplit(database_url)
    if not parts.hostname or not parts.path.strip("/"):
        raise ConfigError(
            f"{DATABASE_URL_ENV} Postgres URLs must include a host and database name."
        )


def _sqlite_path_from_url(database_url: str, project_root: Path) -> Path:
    supported_prefixes = ("sqlite:///", "sqlite+aiosqlite:///")
    matched_prefix = next(
        (prefix for prefix in supported_prefixes if database_url.startswith(prefix)),
        None,
    )
    if matched_prefix is None:
        raise ConfigError(
            f"{DATABASE_URL_ENV} must start with sqlite:/// for the MVP SQLite backend."
        )

    raw_path = database_url.removeprefix(matched_prefix)
    if raw_path == ":memory:":
        return Path(raw_path)
    if not raw_path:
        raise ConfigError(f"{DATABASE_URL_ENV} must include a SQLite database file path.")

    return _resolve_database_path(raw_path, project_root)


def _resolve_database_path(raw_path: str, project_root: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path == Path(":memory:"):
        return path
    if path.is_absolute():
        return path
    return project_root / path


def _database_url_for_path(database_path: Path) -> str:
    if database_path == Path(":memory:"):
        return "sqlite:///:memory:"
    return f"sqlite:///{database_path}"
