"""WSGI API surface for Idea Inbox."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from idea_inbox.capabilities.registry import CapabilityRegistry
from idea_inbox.config import AppConfig, ConfigError, load_config
from idea_inbox.connectors.webhook import GenericWebhookConnector
from idea_inbox.core.capabilities import CapabilityStatus
from idea_inbox.core.manual_capture import (
    ManualIdeaPayload,
    ManualIdeaValidationError,
    validate_manual_idea_payload,
)
from idea_inbox.core.models import EmptySearchQuery, SearchLimitError
from idea_inbox.core.ports import ModelProvider
from idea_inbox.core.query import (
    QueryValidationError,
    answer_query,
    validate_query_request,
)
from idea_inbox.core.services import create_manual_idea, ingest_connector_event
from idea_inbox.search.sqlite_fts import DEFAULT_LIMIT, MAX_LIMIT, SQLiteFTSSearchIndex
from idea_inbox.storage.sqlite import SQLiteMigrationError, SQLiteStorageBackend

QUERY_DISABLED_REASON = "Enable and configure the query-ai capability before using POST /v1/query."
GENERIC_WEBHOOK_CAPABILITY = "generic-webhook-connector"
GENERIC_WEBHOOK_DISABLED_REASON = (
    "Enable the generic-webhook-connector capability before using "
    "POST /v1/connectors/webhook/generic."
)

StartResponse = Callable[[str, list[tuple[str, str]]], None]
WSGIApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


def create_app(
    config: AppConfig | None = None,
    *,
    database_path: str | Path | None = None,
    capability_registry: CapabilityRegistry | None = None,
    model_provider: ModelProvider | None = None,
) -> WSGIApp:
    """Create a small WSGI app backed by the configured SQLite database."""
    if config is not None and database_path is not None:
        raise ConfigError("Pass either config or database_path, not both.")
    resolved_database_path = (
        Path(database_path)
        if database_path is not None
        else (config or load_config()).database_path
    )
    resolved_capability_registry = capability_registry or CapabilityRegistry()

    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD")
        path = environ.get("PATH_INFO")

        if method == "POST" and path == "/v1/ideas":
            return _create_manual_idea_response(start_response, environ, resolved_database_path)

        if method == "POST" and path == "/v1/query":
            return _query_response(
                start_response,
                environ,
                resolved_database_path,
                resolved_capability_registry,
                model_provider,
            )

        if method == "POST" and path == "/v1/connectors/webhook/generic":
            return _generic_webhook_response(
                start_response,
                environ,
                resolved_database_path,
                resolved_capability_registry,
            )

        if method != "GET" or path != "/v1/ideas/search":
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


def _generic_webhook_response(
    start_response: StartResponse,
    environ: dict[str, Any],
    database_path: str | Path,
    capability_registry: CapabilityRegistry,
) -> list[bytes]:
    capability = capability_registry.get_capability(GENERIC_WEBHOOK_CAPABILITY)
    if capability is None or capability.status != CapabilityStatus.ENABLED:
        status = capability.status.value if capability is not None else "unavailable"
        return _json_response(
            start_response,
            "503 Service Unavailable",
            _error(
                "CAPABILITY_DISABLED",
                "Generic webhook ingestion is not enabled for this Idea Inbox instance.",
                {
                    "capability": GENERIC_WEBHOOK_CAPABILITY,
                    "status": status,
                    "reason": GENERIC_WEBHOOK_DISABLED_REASON,
                },
            ),
        )

    try:
        payload = _create_generic_webhook_payload(database_path, _read_json_body(environ))
    except ManualIdeaValidationError as exc:
        return _json_response(
            start_response,
            "400 Bad Request",
            _error("VALIDATION_ERROR", exc.message, {"field": exc.field}),
        )
    except (OSError, sqlite3.Error, SQLiteMigrationError):
        return _json_response(
            start_response,
            "500 Internal Server Error",
            _error("STORAGE_ERROR", "Webhook event could not be saved.", {}),
        )

    return _json_response(start_response, "201 Created", payload)


def _query_response(
    start_response: StartResponse,
    environ: dict[str, Any],
    database_path: str | Path,
    capability_registry: CapabilityRegistry,
    model_provider: ModelProvider | None,
) -> list[bytes]:
    capability = capability_registry.get_capability("query-ai")
    if capability is None or capability.status != CapabilityStatus.ENABLED:
        status = capability.status.value if capability is not None else "unavailable"
        return _json_response(
            start_response,
            "503 Service Unavailable",
            _error(
                "CAPABILITY_DISABLED",
                "Cited query is not enabled for this Idea Inbox instance.",
                {
                    "capability": "query-ai",
                    "status": status,
                    "reason": QUERY_DISABLED_REASON,
                },
            ),
        )

    try:
        request = validate_query_request(_read_json_body(environ))
        payload = _query_payload(database_path, request, model_provider)
    except ManualIdeaValidationError as exc:
        return _json_response(
            start_response,
            "400 Bad Request",
            _error("VALIDATION_ERROR", exc.message, {"field": exc.field}),
        )
    except QueryValidationError as exc:
        return _json_response(
            start_response,
            "400 Bad Request",
            _error("VALIDATION_ERROR", exc.message, {"field": exc.field}),
        )
    except (EmptySearchQuery, SearchLimitError):
        return _json_response(
            start_response,
            "400 Bad Request",
            _error(
                "VALIDATION_ERROR",
                f"Query limit must be between 1 and {MAX_LIMIT}.",
                {"field": "limit"},
            ),
        )
    except ValueError:
        return _json_response(
            start_response,
            "502 Bad Gateway",
            _error(
                "PROVIDER_ERROR",
                "Query provider could not answer the request.",
                {"provider": getattr(model_provider, "provider_name", None)},
            ),
        )
    except (OSError, sqlite3.Error, SQLiteMigrationError):
        return _json_response(
            start_response,
            "500 Internal Server Error",
            _error("STORAGE_ERROR", "Query could not be answered.", {}),
        )

    return _json_response(start_response, "200 OK", payload)


def _query_payload(
    database_path: str | Path, request: Any, model_provider: ModelProvider | None
) -> dict[str, Any]:
    storage = SQLiteStorageBackend(database_path)
    try:
        storage.migrate()
        result = answer_query(
            storage=storage,
            search_index=SQLiteFTSSearchIndex(storage),
            request=request,
            answerer=model_provider,
        )
    finally:
        storage.close()

    return {
        "answer": {"message": result.answer.message, "grounding": result.answer.grounding},
        "citations": result.citations,
        "hits": result.hits,
        "meta": result.meta,
    }


def _create_manual_idea_response(
    start_response: StartResponse,
    environ: dict[str, Any],
    database_path: str | Path,
) -> list[bytes]:
    try:
        body = _read_json_body(environ)
        manual_payload = validate_manual_idea_payload(body)
        payload = _create_manual_idea_payload(database_path, manual_payload)
    except ManualIdeaValidationError as exc:
        return _json_response(
            start_response,
            "400 Bad Request",
            _error("VALIDATION_ERROR", exc.message, {"field": exc.field}),
        )
    except (OSError, sqlite3.Error, SQLiteMigrationError):
        return _json_response(
            start_response,
            "500 Internal Server Error",
            _error("STORAGE_ERROR", "Idea could not be saved.", {}),
        )

    return _json_response(start_response, "201 Created", payload)


def _read_json_body(environ: dict[str, Any]) -> Any:
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError as exc:
        raise ManualIdeaValidationError("Request body must be valid JSON.", "body") from exc
    body = environ["wsgi.input"].read(length)
    try:
        return json.loads(body.decode("utf-8") or "null")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManualIdeaValidationError("Request body must be valid JSON.", "body") from exc


def _create_manual_idea_payload(
    database_path: str | Path, manual_payload: ManualIdeaPayload
) -> dict[str, Any]:
    storage = SQLiteStorageBackend(database_path)
    try:
        storage.migrate()
        result = create_manual_idea(storage, manual_payload)
    finally:
        storage.close()

    return {
        "item": {
            "idea_id": result.idea.id,
            "text": result.idea.text,
            "source": result.idea.source,
            "source_ref": result.idea.source_ref,
            "captured_at": result.idea.captured_at,
            "metadata": result.idea.metadata,
            "tags": list(result.idea.tags),
        }
    }


def _create_generic_webhook_payload(database_path: str | Path, body: Any) -> dict[str, Any]:
    storage = SQLiteStorageBackend(database_path)
    try:
        storage.migrate()
        result = ingest_connector_event(storage, GenericWebhookConnector(), body)
    finally:
        storage.close()

    return {
        "item": {
            "idea_id": result.ideas[0].id,
            "text": result.ideas[0].text,
            "source": result.ideas[0].source,
            "source_ref": result.ideas[0].source_ref,
            "captured_at": result.ideas[0].captured_at,
            "metadata": result.ideas[0].metadata,
            "tags": list(result.ideas[0].tags),
        }
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
