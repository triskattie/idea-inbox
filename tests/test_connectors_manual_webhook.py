import json

import pytest

from idea_inbox.connectors.manual import ManualConnector
from idea_inbox.connectors.webhook import GenericWebhookConnector
from idea_inbox.core.services import ingest_connector_event
from idea_inbox.storage.sqlite import SQLiteStorageBackend


@pytest.fixture
def storage(tmp_path):
    backend = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")
    backend.migrate()
    try:
        yield backend
    finally:
        backend.close()


def test_manual_connector_ingests_raw_event_draft_and_idea(storage: SQLiteStorageBackend) -> None:
    result = ingest_connector_event(
        storage,
        ManualConnector(),
        {
            "text": "Capture this direct operator idea.",
            "source_ref": "manual-note-8",
            "actor_ref": "operator-1",
            "metadata": {"surface": "manual-adapter-test"},
            "tags": ["Capture"],
        },
    )

    raw_event = storage.get_raw_event(result.raw_event.id)
    drafts = storage.list_idea_drafts(raw_event_id=result.raw_event.id)
    idea = storage.get_idea(result.ideas[0].id)

    assert raw_event is not None
    assert idea is not None
    assert raw_event.source == "manual"
    assert raw_event.provider_event_id == "manual-note-8"
    assert raw_event.processing_state == "processed"
    assert json.loads(raw_event.payload)["text"] == "Capture this direct operator idea."
    assert [draft.text for draft in drafts] == ["Capture this direct operator idea."]
    assert idea.raw_event_id == raw_event.id
    assert idea.draft_id == drafts[0].id
    assert idea.source == "manual"
    assert idea.source_ref == "manual-note-8"
    assert idea.tags == ("capture",)


def test_webhook_connector_preserves_provider_id_verbatim_for_idempotency(
    storage: SQLiteStorageBackend,
) -> None:
    connector = GenericWebhookConnector()
    payload = {
        "event_id": " Provider Event 42 / unchanged ",
        "text": "Webhook idea body.",
        "source_ref": "https://example.test/events/42",
        "actor_ref": "external-system",
        "occurred_at": "2026-08-22T12:30:00Z",
        "metadata": {"provider": "generic-test"},
        "tags": ["Webhook"],
    }

    first = ingest_connector_event(storage, connector, payload)
    duplicate = ingest_connector_event(storage, connector, {**payload, "text": "Retried body"})

    assert duplicate.raw_event.id == first.raw_event.id
    assert duplicate.drafts[0].id == first.drafts[0].id
    assert duplicate.ideas[0].id == first.ideas[0].id
    assert duplicate.ideas[0].text == "Webhook idea body."
    assert duplicate.raw_event.provider_event_id == " Provider Event 42 / unchanged "
    assert duplicate.raw_event.dedupe_key == " Provider Event 42 / unchanged "
    assert storage.count_raw_events() == 1
    assert storage.list_idea_drafts(raw_event_id=first.raw_event.id) == list(first.drafts)
    assert [idea.id for idea in storage.list_ideas()] == [first.ideas[0].id]


def test_webhook_connector_uses_payload_hash_idempotency_when_provider_id_is_absent(
    storage: SQLiteStorageBackend,
) -> None:
    payload = {"text": "Provider-less webhook idea.", "metadata": {"source": "test"}}

    first = ingest_connector_event(storage, GenericWebhookConnector(), payload)
    duplicate = ingest_connector_event(storage, GenericWebhookConnector(), payload)

    assert duplicate.raw_event.id == first.raw_event.id
    assert duplicate.ideas[0].id == first.ideas[0].id
    assert storage.count_raw_events() == 1
