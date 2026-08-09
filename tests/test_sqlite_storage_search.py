import importlib

import pytest

import idea_inbox.storage.sqlite as sqlite_storage
from idea_inbox.core.models import EmptySearchQuery, Idea, RawEvent
from idea_inbox.search.sqlite_fts import SQLiteFTSSearchIndex
from idea_inbox.storage.sqlite import SQLiteStorageBackend


@pytest.fixture
def storage(tmp_path):
    backend = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")
    backend.migrate()
    return backend


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
        payload='{"text": "raw-only hidden payload term"}',
        payload_hash=f"hash-{event_id}",
        processing_state="pending",
        error_code=None,
        error_message=None,
    )


def idea(
    idea_id: str,
    raw_event_id: str = "raw_1",
    text: str = "local AI inbox idea",
    tags: tuple[str, ...] = (),
    source_ref: str | None = None,
    captured_at: str = "2026-08-09T00:00:00Z",
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
        tags=tags,
        embedding_state="not_requested",
    )


def test_migrations_create_authoritative_tables_and_fts_index_idempotently(storage) -> None:
    storage.migrate()

    tables = set(storage.table_names())

    assert {"schema_migrations", "raw_events", "ideas", "idea_fts"} <= tables
    assert storage.applied_migration_versions() == ["0001_initial_storage", "0002_idea_fts"]


def test_core_contract_modules_do_not_import_sqlite() -> None:
    for module_name in ["idea_inbox.core.models", "idea_inbox.core.ports"]:
        module = importlib.import_module(module_name)
        module_source_names = {name for name in module.__dict__ if "sqlite" in name.lower()}

        assert module_source_names == set()


def test_migration_fails_with_actionable_error_when_fts5_is_unavailable(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sqlite_storage, "_has_fts5", lambda _connection: False)
    storage = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")

    with pytest.raises(sqlite_storage.SQLiteMigrationError, match="SQLite FTS5 is not available"):
        storage.migrate()


def test_saving_duplicate_raw_event_preserves_existing_record(storage) -> None:
    first = storage.save_raw_event(raw_event("raw_1", "dedupe-1"))
    duplicate = storage.save_raw_event(raw_event("raw_2", "dedupe-1"))

    assert duplicate.id == first.id
    assert storage.count_raw_events() == 1


def test_inserted_idea_is_searchable_with_stable_hit_fields(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(idea("idea_1", text="Local AI should run on a Pi cluster"))
    search = SQLiteFTSSearchIndex(storage)

    hits = search.search("local", limit=10)

    assert [hit.idea_id for hit in hits] == ["idea_1"]
    assert hits[0].rank == 1
    assert hits[0].source == "manual"
    assert hits[0].captured_at == "2026-08-09T00:00:00Z"
    assert "<mark>Local</mark>" in hits[0].snippet
    assert isinstance(hits[0].score, float)


def test_search_ranking_is_deterministic_and_respects_limit(storage) -> None:
    storage.save_raw_event(raw_event("raw_1"))
    storage.save_raw_event(raw_event("raw_2"))
    storage.save_raw_event(raw_event("raw_3"))
    storage.save_idea(
        idea("idea_older", "raw_1", "local notes", captured_at="2026-08-08T00:00:00Z")
    )
    storage.save_idea(
        idea(
            "idea_relevant",
            "raw_2",
            "local AI local assistant local search",
            captured_at="2026-08-07T00:00:00Z",
        )
    )
    storage.save_idea(
        idea("idea_newer", "raw_3", "local inbox", captured_at="2026-08-09T00:00:00Z")
    )
    search = SQLiteFTSSearchIndex(storage)

    hits = search.search("local", limit=2)

    assert [hit.idea_id for hit in hits] == ["idea_relevant", "idea_newer"]
    assert [hit.rank for hit in hits] == [1, 2]


def test_search_returns_empty_for_no_results_and_rejects_empty_queries(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(idea("idea_1", text="offline first storage"))
    search = SQLiteFTSSearchIndex(storage)

    assert search.search("nonexistent", limit=10) == []
    with pytest.raises(EmptySearchQuery):
        search.search("  \t ", limit=10)


def test_updated_idea_replaces_old_fts_terms(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(idea("idea_1", text="local AI inbox idea"))
    storage.save_idea(idea("idea_1", text="garden planning note"))
    search = SQLiteFTSSearchIndex(storage)

    assert search.search("local", limit=10) == []
    assert [hit.idea_id for hit in search.search("garden", limit=10)] == ["idea_1"]


def test_deleted_idea_is_removed_from_search_but_raw_event_remains(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(idea("idea_1", text="local AI inbox idea"))
    storage.delete_idea("idea_1")
    search = SQLiteFTSSearchIndex(storage)

    assert search.search("local", limit=10) == []
    assert storage.get_raw_event("raw_1") is not None


def test_rebuild_restores_search_projection(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(idea("idea_1", text="local AI inbox idea"))
    storage.clear_fts_projection_for_test()
    search = SQLiteFTSSearchIndex(storage)

    assert search.search("local", limit=10) == []

    search.rebuild()

    assert [hit.idea_id for hit in search.search("local", limit=10)] == ["idea_1"]


def test_tags_and_source_ref_are_searchable_but_raw_payload_is_not(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(
        idea(
            "idea_1",
            text="deploy a small capture service",
            tags=("homelab", "sqlite"),
            source_ref="raspberry pi note",
        )
    )
    search = SQLiteFTSSearchIndex(storage)

    assert [hit.idea_id for hit in search.search("homelab", limit=10)] == ["idea_1"]
    assert [hit.idea_id for hit in search.search("raspberry", limit=10)] == ["idea_1"]
    assert search.search("hidden", limit=10) == []


def test_punctuation_heavy_query_does_not_crash(storage) -> None:
    storage.save_raw_event(raw_event())
    storage.save_idea(idea("idea_1", text="local AI inbox idea"))
    search = SQLiteFTSSearchIndex(storage)

    assert [hit.idea_id for hit in search.search("local!!!", limit=10)] == ["idea_1"]
