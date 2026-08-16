import json
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

import pytest

from idea_inbox.api import create_app
from idea_inbox.storage.sqlite import SQLiteStorageBackend


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
            "PATH_INFO": path,
            "QUERY_STRING": "",
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


def test_manual_idea_create_endpoint_accepts_text_and_returns_boundary_shape(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    app = create_app(database_path=database_path)

    status, headers, payload = request(
        app,
        "/v1/ideas",
        json_body={
            "text": "Remember to prototype local-first capture before connector work.",
            "source_ref": "manual-note-1",
            "actor_ref": "local-operator",
            "metadata": {"surface": "api-test"},
            "tags": ["local-ai", "capture"],
        },
    )

    assert status == "201 Created"
    assert headers["Content-Type"] == "application/json"
    assert payload == {
        "item": {
            "idea_id": payload["item"]["idea_id"],
            "text": "Remember to prototype local-first capture before connector work.",
            "source": "manual",
            "source_ref": "manual-note-1",
            "captured_at": payload["item"]["captured_at"],
            "metadata": {"surface": "api-test"},
            "tags": ["local-ai", "capture"],
        }
    }
    assert isinstance(payload["item"]["idea_id"], str)
    assert payload["item"]["idea_id"]
    assert isinstance(payload["item"]["captured_at"], str)

    storage = SQLiteStorageBackend(database_path)
    try:
        assert storage.count_raw_events() == 1
        raw_rows = storage.connection.execute("SELECT * FROM raw_events").fetchall()
        idea_rows = storage.connection.execute("SELECT * FROM ideas").fetchall()
    finally:
        storage.close()
    assert len(raw_rows) == 1
    assert len(idea_rows) == 1
    assert raw_rows[0]["source"] == "manual"
    assert raw_rows[0]["actor_ref"] == "local-operator"
    assert json.loads(raw_rows[0]["payload"])["text"] == payload["item"]["text"]
    assert idea_rows[0]["raw_event_id"] == raw_rows[0]["id"]


@pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "   \n\t  "}])
def test_manual_idea_create_endpoint_rejects_missing_or_blank_text(
    tmp_path: Path,
    body: dict,
) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, _headers, payload = request(app, "/v1/ideas", json_body=body)

    assert status == "400 Bad Request"
    assert payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Idea text must not be empty.",
            "details": {"field": "text"},
        }
    }


def test_manual_idea_create_endpoint_rejects_non_object_body_with_useful_error(
    tmp_path: Path,
) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, _headers, payload = request(app, "/v1/ideas", raw_body=b'"not an object"')

    assert status == "400 Bad Request"
    assert payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a JSON object.",
            "details": {"field": "body"},
        }
    }


def test_manual_idea_create_endpoint_rejects_invalid_optional_metadata(
    tmp_path: Path,
) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, _headers, payload = request(
        app,
        "/v1/ideas",
        json_body={"text": "Valid idea text", "metadata": "not an object"},
    )

    assert status == "400 Bad Request"
    assert payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Idea metadata must be a JSON object.",
            "details": {"field": "metadata"},
        }
    }


def test_manual_idea_create_endpoint_trims_reusable_payload_fields(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, _headers, payload = request(
        app,
        "/v1/ideas",
        json_body={
            "text": "  Trim this idea before storing.  ",
            "source_ref": "  manual-note-2  ",
            "actor_ref": "  local-operator  ",
            "tags": [" Local-AI ", "capture", "local-ai", "  "],
        },
    )

    assert status == "201 Created"
    assert payload["item"]["text"] == "Trim this idea before storing."
    assert payload["item"]["source_ref"] == "manual-note-2"
    assert payload["item"]["tags"] == ["local-ai", "capture"]


def test_manual_idea_create_endpoint_replays_duplicate_request_idempotently(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    app = create_app(database_path=database_path)
    body = {
        "text": "Replay should return the existing idea.",
        "source_ref": "manual-note-3",
        "actor_ref": "local-operator",
        "tags": ["capture"],
    }

    first_status, _headers, first_payload = request(app, "/v1/ideas", json_body=body)
    second_status, _headers, second_payload = request(app, "/v1/ideas", json_body=body)

    assert first_status == "201 Created"
    assert second_status == "201 Created"
    assert second_payload == first_payload

    storage = SQLiteStorageBackend(database_path)
    try:
        raw_count = storage.count_raw_events()
        ideas = storage.list_ideas()
    finally:
        storage.close()
    assert raw_count == 1
    assert [idea.id for idea in ideas] == [first_payload["item"]["idea_id"]]


def test_manual_idea_create_endpoint_accepts_idempotency_key(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    app = create_app(database_path=database_path)

    first_status, _headers, first_payload = request(
        app,
        "/v1/ideas",
        json_body={"text": "Original body", "idempotency_key": "manual-key-1"},
    )
    second_status, _headers, second_payload = request(
        app,
        "/v1/ideas",
        json_body={"text": "Retried changed body", "idempotency_key": "manual-key-1"},
    )

    assert first_status == "201 Created"
    assert second_status == "201 Created"
    assert second_payload == first_payload

    storage = SQLiteStorageBackend(database_path)
    try:
        raw_rows = storage.connection.execute("SELECT dedupe_key FROM raw_events").fetchall()
        ideas = storage.list_ideas()
    finally:
        storage.close()
    assert [row["dedupe_key"] for row in raw_rows] == ["manual-key-1"]
    assert [idea.text for idea in ideas] == ["Original body"]


def test_manual_idea_create_endpoint_rejects_malformed_optional_fields(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    invalid_cases = [
        (
            {"text": "Valid idea text", "source_ref": 42},
            "source_ref",
            "Idea source_ref must be a string.",
        ),
        (
            {"text": "Valid idea text", "actor_ref": 42},
            "actor_ref",
            "Idea actor_ref must be a string.",
        ),
        (
            {"text": "Valid idea text", "tags": "local-ai"},
            "tags",
            "Idea tags must be a list of strings.",
        ),
        (
            {"text": "Valid idea text", "tags": ["ok", 42]},
            "tags",
            "Idea tags must be a list of strings.",
        ),
    ]
    for body, field, message in invalid_cases:
        status, _headers, payload = request(app, "/v1/ideas", json_body=body)

        assert status == "400 Bad Request"
        assert payload == {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "details": {"field": field},
            }
        }
