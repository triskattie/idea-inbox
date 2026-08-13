from dataclasses import replace

from idea_inbox.core.models import Idea, IdeaDraft, RawEvent
from idea_inbox.storage.sqlite import SQLiteStorageBackend


def raw_event(event_id: str = "raw_1", *, state: str = "pending") -> RawEvent:
    return RawEvent(
        id=event_id,
        source="manual",
        provider_event_id="provider-1",
        dedupe_key=f"dedupe-{event_id}",
        received_at="2026-08-09T00:00:00Z",
        occurred_at="2026-08-08T23:59:00Z",
        actor_ref="tester",
        payload='{"text":"build local-first idea inbox"}',
        payload_hash=f"hash-{event_id}",
        processing_state=state,
    )


def idea_draft(draft_id: str = "draft_1", raw_event_id: str = "raw_1") -> IdeaDraft:
    return IdeaDraft(
        id=draft_id,
        raw_event_id=raw_event_id,
        text="build local-first idea inbox",
        source_created_at="2026-08-08T23:59:00Z",
        source_uri="manual:tester",
        metadata={"kind": "manual"},
        extraction_state="accepted",
    )


def idea(idea_id: str = "idea_1", raw_event_id: str = "raw_1", draft_id: str = "draft_1") -> Idea:
    return Idea(
        id=idea_id,
        raw_event_id=raw_event_id,
        draft_id=draft_id,
        text="build local-first idea inbox",
        source="manual",
        source_ref="manual:tester",
        captured_at="2026-08-08T23:59:00Z",
        created_at="2026-08-09T00:00:01Z",
        updated_at="2026-08-09T00:00:01Z",
        metadata={"kind": "manual"},
        tags=("sqlite", "local-first"),
        embedding_state="not_requested",
    )


def test_sqlite_storage_creates_reads_updates_and_lists_authoritative_records(tmp_path) -> None:
    storage = SQLiteStorageBackend(tmp_path / "idea-inbox.sqlite3")
    try:
        storage.migrate()

        stored_raw = storage.save_raw_event(raw_event())
        stored_draft = storage.save_idea_draft(idea_draft())
        stored_idea = storage.save_idea(idea())
        updated_raw = storage.update_raw_event_processing_state(
            "raw_1",
            "processed",
            error_code=None,
            error_message=None,
        )
        updated_idea = storage.save_idea(
            replace(
                idea(),
                text="build SQLite-backed idea inbox",
                updated_at="2026-08-09T00:01:00Z",
                tags=("sqlite", "storage"),
            )
        )

        assert stored_raw.id == "raw_1"
        assert stored_draft.id == "draft_1"
        assert stored_idea.id == "idea_1"
        assert updated_raw is not None
        assert updated_raw.processing_state == "processed"
        assert updated_idea.text == "build SQLite-backed idea inbox"
        assert updated_idea.tags == ("sqlite", "storage")
        assert storage.get_raw_event("raw_1") == updated_raw
        assert storage.get_idea_draft("draft_1") == stored_draft
        assert storage.get_idea("idea_1") == updated_idea
        assert storage.list_raw_events() == [updated_raw]
        assert storage.list_idea_drafts(raw_event_id="raw_1") == [stored_draft]
        assert storage.list_ideas() == [updated_idea]
        stored_tags = storage.connection.execute(
            "SELECT tag FROM idea_tags WHERE idea_id = ? ORDER BY tag",
            ("idea_1",),
        ).fetchall()
        assert [row["tag"] for row in stored_tags] == ["sqlite", "storage"]
    finally:
        storage.close()


def test_sqlite_storage_lists_records_with_filters_and_pagination(tmp_path) -> None:
    storage = SQLiteStorageBackend(tmp_path / "idea-inbox.sqlite3")
    try:
        storage.migrate()
        storage.save_raw_event(raw_event("raw_1", state="processed"))
        storage.save_raw_event(raw_event("raw_2", state="pending"))
        storage.save_idea_draft(idea_draft("draft_1", "raw_1"))
        storage.save_idea_draft(idea_draft("draft_2", "raw_2"))
        storage.save_idea(
            replace(idea("idea_older", "raw_1", "draft_1"), captured_at="2026-08-07T00:00:00Z")
        )
        storage.save_idea(
            replace(idea("idea_newer", "raw_2", "draft_2"), captured_at="2026-08-09T00:00:00Z")
        )

        assert [event.id for event in storage.list_raw_events(processing_state="pending")] == [
            "raw_2"
        ]
        assert [draft.id for draft in storage.list_idea_drafts(raw_event_id="raw_2")] == ["draft_2"]
        assert [stored.id for stored in storage.list_ideas(limit=1)] == ["idea_newer"]
        assert [stored.id for stored in storage.list_ideas(limit=1, offset=1)] == ["idea_older"]
    finally:
        storage.close()
