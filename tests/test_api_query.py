import json
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any
from wsgiref.util import setup_testing_defaults

from idea_inbox.api import create_app
from idea_inbox.capabilities.registry import CapabilityRegistry
from idea_inbox.core.models import Idea, IdeaDraft, RawEvent
from idea_inbox.providers.capabilities import provider_capabilities
from idea_inbox.providers.mock import MockModelProvider
from idea_inbox.storage.sqlite import SQLiteStorageBackend


class BrokenModelProvider:
    mode: str = "broken"
    provider_name: str | None = "broken"

    def answer(
        self,
        *,
        query: str,
        evidence: Sequence[Any],
        options: Any = None,
    ) -> Any:
        raise ValueError("provider response malformed")


DISABLED_QUERY_REASON = "Enable and configure the query-ai capability before using POST /v1/query."


def raw_event(event_id: str, text: str) -> RawEvent:
    return RawEvent(
        id=event_id,
        source="manual",
        provider_event_id=None,
        dedupe_key=event_id,
        received_at="2026-08-09T00:00:00Z",
        occurred_at=None,
        actor_ref="tester",
        payload=json.dumps({"text": text, "internal_note": "raw payload must stay private"}),
        payload_hash=f"hash-{event_id}",
        processing_state="processed",
        error_code=None,
        error_message=None,
    )


def idea_draft(draft_id: str, raw_event_id: str, text: str) -> IdeaDraft:
    return IdeaDraft(
        id=draft_id,
        raw_event_id=raw_event_id,
        text=text,
        source_created_at="2026-08-08T00:00:00Z",
        source_uri="manual-note://local-ai",
        metadata={"surface": "api-test"},
        extraction_state="accepted",
    )


def idea(
    idea_id: str,
    raw_event_id: str,
    draft_id: str,
    text: str,
    source_ref: str | None = None,
) -> Idea:
    return Idea(
        id=idea_id,
        raw_event_id=raw_event_id,
        draft_id=draft_id,
        text=text,
        source="manual",
        source_ref=source_ref,
        captured_at="2026-08-08T00:00:00Z",
        created_at="2026-08-08T00:00:00Z",
        updated_at="2026-08-08T00:00:00Z",
        metadata={"surface": "api-test"},
        tags=("local-ai",),
        embedding_state="not_requested",
    )


def seed_query_database(database_path: Path) -> None:
    storage = SQLiteStorageBackend(database_path)
    try:
        storage.migrate()
        storage.save_raw_event(raw_event("raw_local_ai", "Prototype local-first capture."))
        storage.save_raw_event(raw_event("raw_garden", "Plan the garden."))
        storage.save_idea_draft(
            idea_draft(
                "draft_local_ai",
                "raw_local_ai",
                "Prototype local-first capture before connector work.",
            )
        )
        storage.save_idea(
            idea(
                "idea_local_ai",
                "raw_local_ai",
                "draft_local_ai",
                "Prototype local-first capture before connector work.",
                "manual-note-1",
            )
        )
        storage.save_idea_draft(idea_draft("draft_garden", "raw_garden", "Plan garden beds."))
        storage.save_idea(
            idea("idea_garden", "raw_garden", "draft_garden", "Plan garden beds.", "garden-1")
        )
    finally:
        storage.close()


def deterministic_query_registry() -> CapabilityRegistry:
    return CapabilityRegistry(
        installed_capabilities=provider_capabilities(),
        enabled_overrides={
            "query-ai": True,
            "model-provider": True,
            "mock-model-provider": True,
            "none-credentials": True,
        },
        config_values={"IDEA_INBOX_CHAT_PROVIDER": "mock"},
    )


def request(
    app,
    path: str,
    *,
    method: str = "POST",
    json_body: dict | None = None,
    raw_body: bytes | None = None,
) -> tuple[str, dict[str, str], dict]:
    body = raw_body or (json.dumps(json_body).encode("utf-8") if json_body is not None else b"")
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "REQUEST_METHOD": method,
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/json",
            "wsgi.input": BytesIO(body),
        }
    )
    response_status = ""
    response_headers: dict[str, str] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        nonlocal response_status, response_headers
        response_status = status
        response_headers = dict(headers)

    response_body = b"".join(app(environ, start_response))
    return response_status, response_headers, json.loads(response_body.decode("utf-8"))


def test_query_endpoint_is_disabled_by_default_without_model_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    for env_name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "IDEA_INBOX_CHAT_PROVIDER",
    ):
        monkeypatch.delenv(env_name, raising=False)
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, headers, payload = request(app, "/v1/query", json_body={"query": "local AI"})

    assert status == "503 Service Unavailable"
    assert headers["Content-Type"] == "application/json"
    assert payload == {
        "error": {
            "code": "CAPABILITY_DISABLED",
            "message": "Cited query is not enabled for this Idea Inbox instance.",
            "details": {
                "capability": "query-ai",
                "status": "disabled",
                "reason": DISABLED_QUERY_REASON,
            },
        }
    }


def test_query_disabled_does_not_break_manual_capture_migrations_or_existing_search(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    app = create_app(database_path=database_path)

    capture_status, _headers, capture_payload = request(
        app,
        "/v1/ideas",
        json_body={"text": "Keep SQLite FTS search healthy while query is disabled."},
    )
    search_status, _headers, search_payload = request(
        app,
        "/v1/ideas/search?q=sqlite&limit=10",
        method="GET",
    )

    assert capture_status == "201 Created"
    assert capture_payload["item"]["source"] == "manual"
    assert search_status == "200 OK"
    assert [item["idea_id"] for item in search_payload["items"]] == [
        capture_payload["item"]["idea_id"]
    ]

    storage = SQLiteStorageBackend(database_path)
    try:
        assert storage.applied_migration_versions() == ["0001", "0002"]
    finally:
        storage.close()


def test_enabled_query_rejects_invalid_request_body_and_limit(tmp_path: Path) -> None:
    app = create_app(
        database_path=tmp_path / "ideas.sqlite3",
        capability_registry=deterministic_query_registry(),
    )

    body_status, _headers, body_payload = request(app, "/v1/query", raw_body=b'"not an object"')
    limit_status, _headers, limit_payload = request(
        app,
        "/v1/query",
        json_body={"query": "local AI", "limit": 0},
    )

    assert body_status == "400 Bad Request"
    assert body_payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a JSON object.",
            "details": {"field": "body"},
        }
    }
    assert limit_status == "400 Bad Request"
    assert limit_payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Query limit must be between 1 and 50.",
            "details": {"field": "limit"},
        }
    }


def test_query_disabled_returns_capability_error_without_reading_body(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, _headers, payload = request(app, "/v1/query", raw_body=b"not-json")

    assert status == "503 Service Unavailable"
    assert payload["error"]["code"] == "CAPABILITY_DISABLED"


def test_enabled_deterministic_query_returns_stored_idea_answer_with_citations(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_query_database(database_path)
    app = create_app(
        database_path=database_path, capability_registry=deterministic_query_registry()
    )

    status, headers, payload = request(
        app,
        "/v1/query",
        json_body={"query": "What did I save about local AI?", "limit": 5},
    )

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert payload["answer"]["grounding"] == "stored_ideas"
    assert "Prototype local-first capture before connector work" in payload["answer"]["message"]
    assert payload["citations"] == [
        {
            "citation_id": "c1",
            "idea_id": "idea_local_ai",
            "snippet": "Prototype local-first capture before connector work.",
            "source": "manual",
            "source_ref": "manual-note-1",
            "captured_at": "2026-08-08T00:00:00Z",
            "provenance": {"raw_event_id": "raw_local_ai", "draft_id": "draft_local_ai"},
        }
    ]
    assert payload["hits"] == [
        {
            "idea_id": "idea_local_ai",
            "rank": 1,
            "score": payload["hits"][0]["score"],
            "snippet": payload["hits"][0]["snippet"],
            "source": "manual",
            "captured_at": "2026-08-08T00:00:00Z",
        }
    ]
    assert isinstance(payload["hits"][0]["score"], float)
    assert "local" in payload["hits"][0]["snippet"].lower()
    assert payload["meta"] == {
        "query": "What did I save about local AI?",
        "limit": 5,
        "grounding": "stored_ideas",
        "answer_mode": "deterministic_mock",
        "model_provider": "mock",
        "retrieval": {"strategy": "sqlite_fts", "evidence_count": 1},
    }
    assert "raw payload must stay private" not in json.dumps(payload)


def test_enabled_query_uses_injected_model_provider_boundary(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_query_database(database_path)
    app = create_app(
        database_path=database_path,
        capability_registry=deterministic_query_registry(),
        model_provider=MockModelProvider(provider_name="mock-injected"),
    )

    status, _headers, payload = request(
        app,
        "/v1/query",
        json_body={"query": "What did I save about local AI?", "limit": 5},
    )

    assert status == "200 OK"
    assert payload["answer"]["grounding"] == "stored_ideas"
    assert payload["meta"]["answer_mode"] == "deterministic_mock"
    assert payload["meta"]["model_provider"] == "mock-injected"


def test_enabled_query_provider_value_error_is_not_reported_as_limit_validation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_query_database(database_path)
    app = create_app(
        database_path=database_path,
        capability_registry=deterministic_query_registry(),
        model_provider=BrokenModelProvider(),
    )

    status, _headers, payload = request(
        app,
        "/v1/query",
        json_body={"query": "What did I save about local AI?", "limit": 5},
    )

    assert status == "502 Bad Gateway"
    assert payload["error"] != {
        "code": "VALIDATION_ERROR",
        "message": "Query limit must be between 1 and 50.",
        "details": {"field": "limit"},
    }
    assert payload["error"]["code"] == "PROVIDER_ERROR"
    assert payload["error"]["details"] == {"provider": "broken"}


def test_enabled_deterministic_query_returns_no_evidence_without_citations(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_query_database(database_path)
    app = create_app(
        database_path=database_path, capability_registry=deterministic_query_registry()
    )

    status, _headers, payload = request(
        app,
        "/v1/query",
        json_body={"query": "Mars colony budgets", "limit": 10},
    )

    assert status == "200 OK"
    assert payload == {
        "answer": {
            "message": "I could not find relevant stored ideas for that query.",
            "grounding": "no_relevant_stored_ideas",
        },
        "citations": [],
        "hits": [],
        "meta": {
            "query": "Mars colony budgets",
            "limit": 10,
            "grounding": "no_relevant_stored_ideas",
            "answer_mode": "deterministic_mock",
            "retrieval": {"strategy": "sqlite_fts", "evidence_count": 0},
        },
    }
