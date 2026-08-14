import json
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from idea_inbox.api import create_app
from idea_inbox.config import AppConfig
from idea_inbox.core.models import Idea, RawEvent
from idea_inbox.storage.sqlite import SQLiteStorageBackend


def raw_event(event_id: str = "raw_1", dedupe_key: str | None = None) -> RawEvent:
    dedupe_key = dedupe_key or event_id
    return RawEvent(
        id=event_id,
        source="manual",
        provider_event_id=None,
        dedupe_key=dedupe_key,
        received_at="2026-08-09T00:00:00Z",
        occurred_at=None,
        actor_ref="tester",
        payload='{"text": "raw-only secret payload"}',
        payload_hash=f"hash-{event_id}",
        processing_state="processed",
        error_code=None,
        error_message=None,
    )


def idea(
    idea_id: str,
    raw_event_id: str,
    text: str,
    captured_at: str,
    source_ref: str | None = None,
) -> Idea:
    return Idea(
        id=idea_id,
        raw_event_id=raw_event_id,
        text=text,
        source="manual",
        source_ref=source_ref,
        captured_at=captured_at,
        created_at=captured_at,
        updated_at=captured_at,
        metadata={},
        tags=(),
        embedding_state="not_requested",
    )


def seed_database(database_path: Path) -> None:
    storage = SQLiteStorageBackend(database_path)
    storage.migrate()
    storage.save_raw_event(raw_event("raw_1"))
    storage.save_raw_event(raw_event("raw_2"))
    storage.save_idea(
        idea(
            "idea_relevant",
            "raw_1",
            "Local AI local assistant search",
            "2026-08-08T00:00:00Z",
        )
    )
    storage.save_idea(idea("idea_other", "raw_2", "Garden planning note", "2026-08-09T00:00:00Z"))
    storage.close()


def request(app, path: str) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
            "wsgi.input": BytesIO(b""),
        }
    )
    response_status = ""
    response_headers: dict[str, str] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        nonlocal response_status, response_headers
        response_status = status
        response_headers = dict(headers)

    body = b"".join(app(environ, start_response))
    return response_status, response_headers, json.loads(body.decode("utf-8"))


def test_search_endpoint_returns_ranked_fts_hits_with_existing_response_shape(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_database(database_path)
    app = create_app(database_path=database_path)

    status, headers, payload = request(app, "/v1/ideas/search?q=local&limit=10")

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert payload == {
        "items": [
            {
                "idea_id": "idea_relevant",
                "snippet": "<mark>Local</mark> AI <mark>local</mark> assistant search",
                "score": payload["items"][0]["score"],
                "source": "manual",
                "captured_at": "2026-08-08T00:00:00Z",
            }
        ],
        "page": {"limit": 10, "next_cursor": None},
    }
    assert isinstance(payload["items"][0]["score"], float)
    assert "secret" not in json.dumps(payload)


def test_search_endpoint_returns_empty_page_for_no_fts_hits(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_database(database_path)
    app = create_app(database_path=database_path)

    status, _headers, payload = request(app, "/v1/ideas/search?q=nonexistent")

    assert status == "200 OK"
    assert payload == {"items": [], "page": {"limit": 10, "next_cursor": None}}


def test_search_endpoint_escapes_user_text_in_highlight_snippets(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    storage = SQLiteStorageBackend(database_path)
    storage.migrate()
    storage.save_raw_event(raw_event("raw_xss"))
    storage.save_idea(
        idea(
            "idea_xss",
            "raw_xss",
            '<script>alert("x")</script> local',
            "2026-08-09T00:00:00Z",
        )
    )
    storage.close()
    app = create_app(database_path=database_path)

    status, _headers, payload = request(app, "/v1/ideas/search?q=local")

    assert status == "200 OK"
    assert payload["items"][0]["snippet"] == (
        '&lt;script&gt;alert("x")&lt;/script&gt; <mark>local</mark>'
    )
    assert "<script>" not in payload["items"][0]["snippet"]


def test_search_app_accepts_canonical_config_database_path(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_database(database_path)
    app = create_app(
        config=AppConfig(
            environment="test",
            log_level="INFO",
            database_url=f"sqlite:///{database_path}",
            database_path=database_path,
        )
    )

    status, _headers, payload = request(app, "/v1/ideas/search?q=garden")

    assert status == "200 OK"
    assert [item["idea_id"] for item in payload["items"]] == ["idea_other"]


def test_search_endpoint_rejects_blank_and_invalid_search_terms_gracefully(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_database(database_path)
    app = create_app(database_path=database_path)

    status, _headers, payload = request(app, "/v1/ideas/search?q=%21%21%21")

    assert status == "400 Bad Request"
    assert payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Search query must not be empty.",
            "details": {"field": "q"},
        }
    }


def test_search_endpoint_rejects_invalid_limits_with_standard_error_shape(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    seed_database(database_path)
    app = create_app(database_path=database_path)

    status, _headers, payload = request(app, "/v1/ideas/search?q=local&limit=0")

    assert status == "400 Bad Request"
    assert payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Search limit must be between 1 and 50.",
            "details": {"field": "limit"},
        }
    }
