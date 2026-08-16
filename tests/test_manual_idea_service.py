import json
from hashlib import sha256

import pytest

from idea_inbox.core.manual_capture import (
    ManualIdeaPayload,
    ManualIdeaValidationError,
    validate_manual_idea_payload,
)
from idea_inbox.core.services import create_manual_idea
from idea_inbox.storage.sqlite import SQLiteStorageBackend


@pytest.fixture
def storage(tmp_path):
    backend = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")
    backend.migrate()
    try:
        yield backend
    finally:
        backend.close()


def test_create_manual_idea_persists_raw_event_draft_and_idea(
    storage: SQLiteStorageBackend,
) -> None:
    result = create_manual_idea(
        storage,
        ManualIdeaPayload(
            text="Prototype local-first manual capture.",
            source_ref="manual-note-1",
            actor_ref="local-operator",
            metadata={"surface": "service-test"},
            tags=("local-ai", "capture"),
        ),
    )

    stored_idea = storage.get_idea(result.idea.id)
    raw_event = storage.get_raw_event(result.raw_event.id)
    drafts = storage.list_idea_drafts(raw_event_id=result.raw_event.id)

    assert raw_event is not None
    assert stored_idea is not None
    assert raw_event.source == "manual"
    assert raw_event.actor_ref == "local-operator"
    assert raw_event.processing_state == "processed"
    assert json.loads(raw_event.payload) == {
        "text": "Prototype local-first manual capture.",
        "idempotency_key": None,
        "source_ref": "manual-note-1",
        "actor_ref": "local-operator",
        "captured_at": None,
        "metadata": {"surface": "service-test"},
        "tags": ["local-ai", "capture"],
    }
    assert raw_event.payload_hash == sha256(raw_event.payload.encode("utf-8")).hexdigest()
    assert [draft.text for draft in drafts] == ["Prototype local-first manual capture."]
    assert stored_idea.raw_event_id == raw_event.id
    assert stored_idea.draft_id == drafts[0].id
    assert stored_idea.text == "Prototype local-first manual capture."
    assert stored_idea.source == "manual"
    assert stored_idea.source_ref == "manual-note-1"
    assert stored_idea.metadata == {"surface": "service-test"}
    assert stored_idea.tags == ("local-ai", "capture")


def test_create_manual_idea_uses_supplied_capture_timestamp(storage: SQLiteStorageBackend) -> None:
    result = create_manual_idea(
        storage,
        ManualIdeaPayload(text="timestamped idea", captured_at="2026-08-14T20:00:00Z"),
    )

    assert result.raw_event.occurred_at == "2026-08-14T20:00:00Z"
    assert result.draft.source_created_at == "2026-08-14T20:00:00Z"
    assert result.idea.captured_at == "2026-08-14T20:00:00Z"


def test_create_manual_idea_is_idempotent_for_duplicate_manual_payload(
    storage: SQLiteStorageBackend,
) -> None:
    payload = ManualIdeaPayload(
        text="Keep manual capture idempotent.",
        source_ref="manual-note-1",
        actor_ref="local-operator",
        captured_at="2026-08-14T20:00:00Z",
        metadata={"surface": "service-test"},
        tags=("capture",),
    )

    first = create_manual_idea(storage, payload)
    duplicate = create_manual_idea(storage, payload)

    assert duplicate.raw_event.id == first.raw_event.id
    assert duplicate.draft.id == first.draft.id
    assert duplicate.idea.id == first.idea.id
    assert storage.count_raw_events() == 1
    assert storage.list_idea_drafts(raw_event_id=first.raw_event.id) == [first.draft]
    assert [idea.id for idea in storage.list_ideas()] == [first.idea.id]


def test_create_manual_idea_uses_explicit_idempotency_key(storage: SQLiteStorageBackend) -> None:
    first = create_manual_idea(
        storage,
        ManualIdeaPayload(text="Original captured text.", idempotency_key="manual-key-1"),
    )
    duplicate = create_manual_idea(
        storage,
        ManualIdeaPayload(text="Changed retry body.", idempotency_key="manual-key-1"),
    )

    assert duplicate.raw_event.id == first.raw_event.id
    assert duplicate.idea.id == first.idea.id
    assert duplicate.idea.text == "Original captured text."
    assert storage.count_raw_events() == 1
    assert [idea.text for idea in storage.list_ideas()] == ["Original captured text."]


def test_validate_manual_idea_payload_rejects_blank_text_before_storage(
    storage: SQLiteStorageBackend,
) -> None:
    with pytest.raises(ManualIdeaValidationError, match="Idea text must not be empty"):
        validate_manual_idea_payload({"text": "  \n\t "})

    assert storage.count_raw_events() == 0
