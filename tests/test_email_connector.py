from __future__ import annotations

from pathlib import Path

import pytest

from idea_inbox.connectors.email import EmailConnector
from idea_inbox.core.services import ingest_connector_event
from idea_inbox.storage.sqlite import SQLiteStorageBackend

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "email"


@pytest.fixture
def storage(tmp_path):
    backend = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")
    backend.migrate()
    try:
        yield backend
    finally:
        backend.close()


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_email_fixture_ingests_raw_event_draft_and_idea(storage: SQLiteStorageBackend) -> None:
    connector = EmailConnector()

    result = ingest_connector_event(storage, connector, fixture("plain_text.eml"))

    assert result.duplicate is False
    assert result.raw_event.source == "email"
    assert result.raw_event.provider_event_id == "<plain-idea-1@example.test>"
    assert result.raw_event.dedupe_key == "<plain-idea-1@example.test>"
    assert result.raw_event.occurred_at == "2026-08-21T10:15:00Z"
    assert result.raw_event.actor_ref == "Ada Lovelace <ada@example.test>"
    assert result.raw_event.processing_state == "processed"
    assert len(result.drafts) == 1
    assert len(result.ideas) == 1
    assert result.drafts[0].text == "Remember to tag captured ideas by source connector."
    assert result.drafts[0].source_uri == "email:<plain-idea-1@example.test>"
    assert result.drafts[0].metadata == {
        "from": "Ada Lovelace <ada@example.test>",
        "message_id": "<plain-idea-1@example.test>",
        "subject": "Prototype inbox tags",
    }
    assert result.ideas[0].source == "email"
    assert result.ideas[0].source_ref == "email:<plain-idea-1@example.test>"
    assert result.ideas[0].text == "Remember to tag captured ideas by source connector."


def test_email_ingest_is_idempotent_by_message_id(storage: SQLiteStorageBackend) -> None:
    connector = EmailConnector()
    raw_message = fixture("plain_text.eml")

    first = ingest_connector_event(storage, connector, raw_message)
    duplicate = ingest_connector_event(storage, connector, raw_message)

    assert duplicate.duplicate is True
    assert duplicate.raw_event.id == first.raw_event.id
    assert [draft.id for draft in duplicate.drafts] == [first.drafts[0].id]
    assert [idea.id for idea in duplicate.ideas] == [first.ideas[0].id]
    assert storage.count_raw_events() == 1
    assert storage.list_idea_drafts(raw_event_id=first.raw_event.id) == list(first.drafts)
    assert storage.list_ideas(raw_event_id=first.raw_event.id) == list(first.ideas)


def test_email_connector_extracts_html_body_and_decodes_encoded_headers(
    storage: SQLiteStorageBackend,
) -> None:
    result = ingest_connector_event(storage, EmailConnector(), fixture("html_encoded.eml"))

    assert result.raw_event.provider_event_id == "<html-idea-2@example.test>"
    assert result.drafts[0].text == "Capture café research links from mail."
    assert result.drafts[0].metadata["subject"] == "HTML café idea"
    assert result.drafts[0].metadata["from"] == "Björn Sender <bjorn@example.test>"


def test_email_connector_accepts_missing_subject_fixture(storage: SQLiteStorageBackend) -> None:
    result = ingest_connector_event(storage, EmailConnector(), fixture("missing_subject.eml"))

    assert result.raw_event.provider_event_id == "<missing-subject-3@example.test>"
    assert result.drafts[0].text == "Inbox items without subjects should still become drafts."
    assert result.drafts[0].metadata == {
        "from": "no-subject@example.test",
        "message_id": "<missing-subject-3@example.test>",
        "subject": None,
    }
