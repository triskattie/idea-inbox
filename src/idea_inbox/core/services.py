"""Core service logic for idea ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from idea_inbox.core.manual_capture import ManualIdeaPayload
from idea_inbox.core.models import Idea, IdeaDraft, RawEvent
from idea_inbox.core.ports import Connector, StorageBackend


@dataclass(frozen=True)
class ManualIdeaResult:
    raw_event: RawEvent
    draft: IdeaDraft
    idea: Idea


@dataclass(frozen=True)
class ConnectorIngestResult:
    raw_event: RawEvent
    drafts: tuple[IdeaDraft, ...]
    ideas: tuple[Idea, ...]
    duplicate: bool = False


def create_manual_idea(storage: StorageBackend, payload: ManualIdeaPayload) -> ManualIdeaResult:
    """Create a first-class idea from validated direct manual input."""
    now = _utc_now()
    captured_at = payload.captured_at or now
    raw_payload = _manual_payload(payload)
    dedupe_key = payload.idempotency_key or sha256(raw_payload.encode("utf-8")).hexdigest()
    raw_event = storage.save_raw_event(
        RawEvent(
            id=_new_id("raw"),
            source="manual",
            provider_event_id=None,
            dedupe_key=dedupe_key,
            received_at=now,
            occurred_at=payload.captured_at,
            actor_ref=payload.actor_ref,
            payload=raw_payload,
            payload_hash=sha256(raw_payload.encode("utf-8")).hexdigest(),
            processing_state="pending",
        )
    )
    existing_ideas = storage.list_ideas(raw_event_id=raw_event.id, limit=1)
    if existing_ideas:
        existing_idea = existing_ideas[0]
        existing_draft = (
            storage.get_idea_draft(existing_idea.draft_id) if existing_idea.draft_id else None
        )
        if existing_draft is None:
            existing_drafts = storage.list_idea_drafts(raw_event_id=raw_event.id, limit=1)
            existing_draft = existing_drafts[0]
        return ManualIdeaResult(raw_event=raw_event, draft=existing_draft, idea=existing_idea)

    draft = storage.save_idea_draft(
        IdeaDraft(
            id=_new_id("draft"),
            raw_event_id=raw_event.id,
            text=payload.text,
            source_created_at=payload.captured_at,
            source_uri=payload.source_ref,
            metadata=payload.metadata,
            extraction_state="accepted",
        )
    )
    idea = storage.save_idea(
        Idea(
            id=_new_id("idea"),
            raw_event_id=raw_event.id,
            draft_id=draft.id,
            text=payload.text,
            source="manual",
            source_ref=payload.source_ref,
            captured_at=captured_at,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata,
            tags=payload.tags,
            embedding_state="not_requested",
        )
    )
    processed_raw_event = storage.update_raw_event_processing_state(raw_event.id, "processed")
    return ManualIdeaResult(raw_event=processed_raw_event or raw_event, draft=draft, idea=idea)


def ingest_connector_event(
    storage: StorageBackend,
    connector: Connector,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
    credentials: object | None = None,
) -> ConnectorIngestResult:
    """Persist one raw event before extracting drafts and canonical ideas.

    Idempotent by the adapter's ``(source, dedupe_key)``: replays return the
    existing raw event lineage without creating duplicates.
    """
    validated_event = connector.validate(payload, headers, credentials)
    raw_event_input = connector.to_raw_event_input(validated_event)
    now = _utc_now()
    raw_event = storage.save_raw_event(
        raw_event_input.to_raw_event(raw_event_id=_new_id("raw"), received_at=now)
    )

    existing_drafts = tuple(storage.list_idea_drafts(raw_event_id=raw_event.id))
    if existing_drafts:
        return ConnectorIngestResult(
            raw_event=raw_event,
            drafts=existing_drafts,
            ideas=tuple(storage.list_ideas(raw_event_id=raw_event.id)),
            duplicate=True,
        )

    drafts: list[IdeaDraft] = []
    ideas: list[Idea] = []
    for draft_input in connector.extract_drafts(raw_event):
        draft = storage.save_idea_draft(
            draft_input.to_idea_draft(raw_event.id, draft_id=_new_id("draft"))
        )
        drafts.append(draft)
        ideas.append(
            storage.save_idea(
                Idea(
                    id=_new_id("idea"),
                    raw_event_id=raw_event.id,
                    draft_id=draft.id,
                    text=draft.text,
                    source=raw_event.source,
                    source_ref=draft.source_uri,
                    captured_at=draft.source_created_at or raw_event.occurred_at or now,
                    created_at=now,
                    updated_at=now,
                    metadata=draft.metadata or {},
                    tags=draft_input.tags,
                    embedding_state="not_requested",
                )
            )
        )
    if not drafts:
        processed = storage.update_raw_event_processing_state(raw_event.id, "processed")
        return ConnectorIngestResult(raw_event=processed or raw_event, drafts=(), ideas=())

    processed_raw_event = storage.update_raw_event_processing_state(raw_event.id, "processed")
    return ConnectorIngestResult(
        raw_event=processed_raw_event or raw_event,
        drafts=tuple(drafts),
        ideas=tuple(ideas),
    )


def _manual_payload(payload: ManualIdeaPayload) -> str:
    return json.dumps(
        {
            "text": payload.text,
            "idempotency_key": payload.idempotency_key,
            "source_ref": payload.source_ref,
            "actor_ref": payload.actor_ref,
            "captured_at": payload.captured_at,
            "metadata": payload.metadata,
            "tags": list(payload.tags),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
