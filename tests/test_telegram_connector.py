from __future__ import annotations

import json
from pathlib import Path

import pytest

from idea_inbox.connectors.telegram import TelegramConnector
from idea_inbox.core.services import ingest_connector_event
from idea_inbox.storage.sqlite import SQLiteStorageBackend

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "telegram"


@pytest.fixture
def storage(tmp_path: Path):
    backend = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")
    backend.migrate()
    try:
        yield backend
    finally:
        backend.close()


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def ingest_fixture(storage: SQLiteStorageBackend, name: str):
    connector = TelegramConnector()
    return ingest_connector_event(storage, connector, load_fixture(name))


def test_telegram_private_message_fixture_creates_raw_event_and_draft(
    storage: SQLiteStorageBackend,
) -> None:
    result = ingest_fixture(storage, "private_text_message.json")

    assert result.raw_event.source == "telegram"
    assert result.raw_event.provider_event_id == "900001001"
    assert result.raw_event.dedupe_key == "900001001"
    assert result.raw_event.actor_ref == "telegram:user:424242"
    assert result.raw_event.occurred_at == "2026-08-22T12:34:56Z"
    assert json.loads(result.raw_event.payload)["message"]["message_id"] == 1001
    assert result.raw_event.processing_state == "processed"
    assert len(result.drafts) == 1
    draft = result.drafts[0]
    assert draft.raw_event_id == result.raw_event.id
    assert draft.text == "Prototype Telegram capture into Idea Inbox."
    assert draft.source_created_at == "2026-08-22T12:34:56Z"
    assert draft.source_uri == "telegram://chat/424242/message/1001"
    assert draft.metadata == {
        "chat_id": 424242,
        "chat_type": "private",
        "message_id": 1001,
        "update_id": 900001001,
        "update_kind": "message",
    }


def test_telegram_group_channel_and_edited_fixtures_parse_offline(
    storage: SQLiteStorageBackend,
) -> None:
    group = ingest_fixture(storage, "group_text_message.json")
    channel = ingest_fixture(storage, "channel_post.json")
    edited = ingest_fixture(storage, "edited_message.json")

    assert [draft.text for draft in group.drafts] == [
        "Group note: test connector idempotency with provider IDs."
    ]
    assert group.raw_event.actor_ref == "telegram:user:515151"
    assert group.drafts[0].source_uri == "telegram://chat/-1009876543210/message/77"
    assert group.drafts[0].metadata["chat_type"] == "supergroup"

    assert [draft.text for draft in channel.drafts] == [
        "Channel idea: keep fixture-driven connectors offline."
    ]
    assert channel.raw_event.actor_ref == "telegram:chat:-1001234567890"
    assert channel.drafts[0].metadata["update_kind"] == "channel_post"

    assert [draft.text for draft in edited.drafts] == [
        "Edited Telegram idea should still parse offline."
    ]
    assert edited.raw_event.provider_event_id == "900001004"
    assert edited.drafts[0].metadata["edit_date"] == "2026-08-22T13:00:00Z"
    assert edited.drafts[0].metadata["update_kind"] == "edited_message"


def test_telegram_non_text_fixture_preserves_raw_event_without_draft(
    storage: SQLiteStorageBackend,
) -> None:
    result = ingest_fixture(storage, "non_text_photo_message.json")

    assert result.raw_event.provider_event_id == "900001005"
    assert result.raw_event.processing_state == "processed"
    assert result.drafts == ()
    assert storage.count_raw_events() == 1
    assert storage.list_idea_drafts(raw_event_id=result.raw_event.id) == []


def test_telegram_fixture_ingestion_is_idempotent_by_provider_update_id(
    storage: SQLiteStorageBackend,
) -> None:
    first = ingest_fixture(storage, "private_text_message.json")
    duplicate = ingest_fixture(storage, "private_text_message.json")

    assert duplicate.raw_event.id == first.raw_event.id
    assert duplicate.drafts == first.drafts
    assert storage.count_raw_events() == 1
    assert storage.list_idea_drafts(raw_event_id=first.raw_event.id) == list(first.drafts)


def test_telegram_connector_implements_core_connector_protocol() -> None:
    connector = TelegramConnector()

    assert connector.source == "telegram"
    assert connector.parse_update(load_fixture("private_text_message.json")) is not None
