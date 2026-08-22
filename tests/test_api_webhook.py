import json
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from idea_inbox.api import create_app
from idea_inbox.capabilities.registry import CapabilityRegistry
from idea_inbox.storage.sqlite import SQLiteStorageBackend


def request(app, path: str, *, json_body: dict | None = None) -> tuple[str, dict]:
    body = json.dumps(json_body or {}).encode("utf-8")
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/json",
            "wsgi.input": BytesIO(body),
        }
    )
    response_status = ""

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        nonlocal response_status
        response_status = status

    response_body = b"".join(app(environ, start_response))
    return response_status, json.loads(response_body.decode("utf-8"))


def test_webhook_ingest_route_rejects_cleanly_when_capability_disabled(
    tmp_path: Path,
) -> None:
    app = create_app(database_path=tmp_path / "ideas.sqlite3")

    status, payload = request(
        app,
        "/v1/connectors/webhook/generic",
        json_body={"event_id": "evt-1", "text": "Disabled webhook."},
    )

    assert status == "503 Service Unavailable"
    assert payload == {
        "error": {
            "code": "CAPABILITY_DISABLED",
            "message": "Generic webhook ingestion is not enabled for this Idea Inbox instance.",
            "details": {
                "capability": "generic-webhook-connector",
                "status": "disabled",
                "reason": (
                    "Enable the generic-webhook-connector capability before using "
                    "POST /v1/connectors/webhook/generic."
                ),
            },
        }
    }


def test_webhook_ingest_route_persists_event_when_capability_enabled(tmp_path: Path) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    registry = CapabilityRegistry(enabled_overrides={"generic-webhook-connector": True})
    app = create_app(database_path=database_path, capability_registry=registry)

    first_status, first_payload = request(
        app,
        "/v1/connectors/webhook/generic",
        json_body={
            "event_id": "evt/generic/1",
            "text": "Webhook route captured idea.",
            "source_ref": "https://example.test/events/1",
            "actor_ref": "webhook-system",
        },
    )
    second_status, second_payload = request(
        app,
        "/v1/connectors/webhook/generic",
        json_body={
            "event_id": "evt/generic/1",
            "text": "Webhook route retry with changed body.",
            "source_ref": "https://example.test/events/1",
            "actor_ref": "webhook-system",
        },
    )

    assert first_status == "201 Created"
    assert second_status == "201 Created"
    assert second_payload == first_payload
    assert first_payload["item"] == {
        "idea_id": first_payload["item"]["idea_id"],
        "text": "Webhook route captured idea.",
        "source": "webhook",
        "source_ref": "https://example.test/events/1",
        "captured_at": first_payload["item"]["captured_at"],
        "metadata": {},
        "tags": [],
    }

    storage = SQLiteStorageBackend(database_path)
    try:
        raw_events = storage.list_raw_events()
        ideas = storage.list_ideas()
    finally:
        storage.close()

    assert len(raw_events) == 1
    assert raw_events[0].provider_event_id == "evt/generic/1"
    assert raw_events[0].dedupe_key == "evt/generic/1"
    assert [idea.id for idea in ideas] == [first_payload["item"]["idea_id"]]
