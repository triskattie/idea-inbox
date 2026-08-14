"""Core service logic for idea ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from idea_inbox.core.manual_capture import ManualIdeaPayload
from idea_inbox.core.models import Idea, IdeaDraft, RawEvent
from idea_inbox.core.ports import StorageBackend


@dataclass(frozen=True)
class ManualIdeaResult:
    raw_event: RawEvent
    draft: IdeaDraft
    idea: Idea


def create_manual_idea(storage: StorageBackend, payload: ManualIdeaPayload) -> ManualIdeaResult:
    """Create a first-class idea from validated direct manual input."""
    now = _utc_now()
    captured_at = payload.captured_at or now
    raw_payload = _manual_payload(payload)
    raw_event = storage.save_raw_event(
        RawEvent(
            id=_new_id("raw"),
            source="manual",
            provider_event_id=None,
            dedupe_key=_new_id("manual"),
            received_at=now,
            occurred_at=payload.captured_at,
            actor_ref=payload.actor_ref,
            payload=raw_payload,
            payload_hash=sha256(raw_payload.encode("utf-8")).hexdigest(),
            processing_state="pending",
        )
    )
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


def _manual_payload(payload: ManualIdeaPayload) -> str:
    return json.dumps(
        {
            "text": payload.text,
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
