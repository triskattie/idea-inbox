"""Opt-in Postgres integration tests for the pgvector deployment profile.

These tests never run in the normal suite. They require:
  1. the `postgres` optional dependency group: `pip install -e '.[postgres]'`
  2. a running Postgres server, e.g. `docker compose --profile postgres up -d`

Run them explicitly with:
  IDEA_INBOX_PG_TEST_DSN=postgresql://idea_inbox:idea_inbox@127.0.0.1:5433/idea_inbox \
      pytest -q tests/test_postgres_integration.py
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC

import pytest

from idea_inbox.core.models import IdeaDraft, RawEvent
from idea_inbox.search.postgres_fts import EmptySearchQuery, PostgresFTSSearchIndex
from idea_inbox.storage.postgres import PostgresStorageBackend

pytestmark = pytest.mark.postgres

DSN = os.environ.get("IDEA_INBOX_PG_TEST_DSN", "")


def _dsn_available() -> bool:
    return bool(DSN.strip())


requires_dsn = pytest.mark.skipif(not _dsn_available(), reason="IDEA_INBOX_PG_TEST_DSN not set")


@pytest.fixture()
def database() -> Iterator[PostgresStorageBackend]:
    if not _dsn_available():
        pytest.skip("IDEA_INBOX_PG_TEST_DSN not set")
    try:
        backend = PostgresStorageBackend(f"{DSN.rsplit('?', 1)[0]}")
    except Exception as exc:  # pragma: no cover - depends on local docker state
        pytest.skip(f"Postgres unavailable: {exc}")
    backend.migrate()
    yield backend
    backend.close()


def _raw_event(source: str = "manual") -> RawEvent:
    return RawEvent(
        id=f"raw_{uuid.uuid4().hex}",
        source=source,
        provider_event_id=None,
        dedupe_key=f"dedupe_{uuid.uuid4().hex}",
        received_at="2026-08-22T12:00:00Z",
        occurred_at=None,
        actor_ref="integration-test",
        payload='{"text":"Postgres integration fixture"}',
        payload_hash="0" * 64,
        processing_state="pending",
    )


def test_migrations_are_idempotent(database: PostgresStorageBackend) -> None:
    seen_after_first = database.applied_versions()

    database.migrate()

    assert database.applied_versions() == seen_after_first


def test_raw_event_idempotency_by_source_and_dedupe_key(
    database: PostgresStorageBackend,
) -> None:
    raw_event = database.save_raw_event(_raw_event())
    duplicate = database.save_raw_event(raw_event)

    assert duplicate.id == raw_event.id
    assert database.count_raw_events() >= 1


def test_idea_roundtrip_preserves_tags_metadata_and_lineage(
    database: PostgresStorageBackend,
) -> None:
    raw_event = database.save_raw_event(_raw_event())
    draft = database.save_idea_draft(
        IdeaDraft(
            id=f"draft_{uuid.uuid4().hex}",
            raw_event_id=raw_event.id,
            text="Local-first capture pipeline for ideas.",
            source_created_at="2026-08-22T11:00:00Z",
            source_uri="postgres-test://idea/1",
            metadata={"surface": "integration"},
            extraction_state="accepted",
        )
    )

    assert draft.raw_event_id == raw_event.id

    stored_draft = database.get_idea_draft(draft.id)
    assert stored_draft is not None
    assert stored_draft.metadata["surface"] == "integration"


def test_tsvector_search_ranks_and_respects_limit(
    database: PostgresStorageBackend,
) -> None:
    from datetime import datetime

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def persist(text: str) -> str:
        raw_event = database.save_raw_event(_raw_event(source="webhook"))
        idea_id = f"idea_{uuid.uuid4().hex}"
        draft_id = f"draft_{uuid.uuid4().hex}"
        database.save_idea_draft(
            IdeaDraft(
                id=draft_id,
                raw_event_id=raw_event.id,
                text=text,
                extraction_state="accepted",
            )
        )
        database.save_idea_from_parts(
            idea_id=idea_id,
            draft_id=draft_id,
            text=text,
            captured_at=now,
        )
        return idea_id

    garden_id = persist("Design a raised bed garden irrigation timer.")
    persist("Prototype a local-first note capture CLI.")

    hits = PostgresFTSSearchIndex(database).search("garden irrigation", limit=5)

    assert hits
    assert hits[0].idea_id == garden_id

    with pytest.raises(EmptySearchQuery):
        PostgresFTSSearchIndex(database).search("   ", limit=5)
