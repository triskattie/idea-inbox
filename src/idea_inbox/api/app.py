"""WSGI API surface for Idea Inbox."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from idea_inbox.config import AppConfig, ConfigError, load_config
from idea_inbox.core.models import EmptySearchQuery, SearchLimitError
from idea_inbox.search.sqlite_fts import DEFAULT_LIMIT, MAX_LIMIT, SQLiteFTSSearchIndex
from idea_inbox.storage.sqlite import SQLiteMigrationError, SQLiteStorageBackend

StartResponse = Callable[[str, list[tuple[str, str]]], None]
WSGIApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


def create_app(
    config: AppConfig | None = None,
    *,
    database_path: str | Path | None = None,
) -> WSGIApp:
    """Create a small WSGI app backed by the configured SQLite database."""
    if config is not None and database_path is not None:
        raise ConfigError("Pass either config or database_path, not both.")
    resolved_database_path = (
        Path(database_path)
        if database_path is not None
        else (config or load_config()).database_path
    )

    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        if environ.get("REQUEST_METHOD") != "GET" or environ.get("PATH_INFO") != "/v1/ideas/search":
            return _json_response(
                start_response,
                "404 Not Found",
                _error("NOT_FOUND", "Endpoint not found.", {}),
            )

        query_params = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        query = query_params.get("q", [""])[0]
        try:
            limit = _parse_limit(query_params.get("limit", [str(DEFAULT_LIMIT)])[0])
            payload = _search_payload(resolved_database_path, query, limit)
        except EmptySearchQuery:
            return _json_response(
                start_response,
                "400 Bad Request",
                _error(
                    "VALIDATION_ERROR",
                    "Search query must not be empty.",
                    {"field": "q"},
                ),
            )
        except (SearchLimitError, ValueError):
            return _json_response(
                start_response,
                "400 Bad Request",
                _error(
                    "VALIDATION_ERROR",
                    f"Search limit must be between 1 and {MAX_LIMIT}.",
                    {"field": "limit"},
                ),
            )
        except SQLiteMigrationError as exc:
            return _json_response(
                start_response,
                "500 Internal Server Error",
                _error("STORAGE_ERROR", str(exc), {}),
            )

        return _json_response(start_response, "200 OK", payload)

    return app


def _parse_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise ValueError("limit must be an integer") from exc
    if not 1 <= limit <= MAX_LIMIT:
        raise SearchLimitError(f"search limit must be between 1 and {MAX_LIMIT}")
    return limit


def _search_payload(database_path: str | Path, query: str, limit: int) -> dict[str, Any]:
    storage = SQLiteStorageBackend(database_path)
    try:
        hits = SQLiteFTSSearchIndex(storage).search(query, limit=limit)
    finally:
        storage.close()

    return {
        "items": [
            {
                "idea_id": hit.idea_id,
                "snippet": hit.snippet,
                "score": hit.score,
                "source": hit.source,
                "captured_at": hit.captured_at,
            }
            for hit in hits
        ],
        "page": {"limit": limit, "next_cursor": None},
    }


def _error(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def _json_response(
    start_response: StartResponse, status: str, payload: dict[str, Any]
) -> list[bytes]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]
