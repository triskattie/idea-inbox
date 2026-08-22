"""Manual direct-submission connector adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from idea_inbox.core.manual_capture import ManualIdeaPayload, validate_manual_idea_payload
from idea_inbox.core.models import RawEvent
from idea_inbox.core.ports import IdeaDraftInput, RawEventInput, ValidatedConnectorEvent


@dataclass(frozen=True)
class ManualConnectorEvent:
    payload: ManualIdeaPayload
    raw_payload: str


class ManualConnector:
    """Connector adapter for operator/user-submitted manual content.

    The first-class `POST /v1/ideas` path stays on the original
    ``create_manual_idea`` service; this adapter exercises the same shared
    ingestion contract used by external connectors.
    """

    name = "manual"

    def validate(
        self,
        payload: Any,
        headers: dict[str, str] | None = None,
        credentials: Any | None = None,
    ) -> ValidatedConnectorEvent:
        del headers, credentials
        manual_payload = validate_manual_idea_payload(payload)
        validated = ManualConnectorEvent(
            payload=manual_payload,
            raw_payload=_manual_payload(manual_payload),
        )
        return ValidatedConnectorEvent(
            source=self.name,
            raw_event=self._raw_event_input(validated),
            drafts=(
                IdeaDraftInput(
                    text=manual_payload.text,
                    source_created_at=manual_payload.captured_at,
                    source_uri=manual_payload.source_ref,
                    metadata=manual_payload.metadata,
                    tags=manual_payload.tags,
                ),
            ),
        )

    def _raw_event_input(self, validated_event: ManualConnectorEvent) -> RawEventInput:
        payload = validated_event.payload
        return RawEventInput(
            source=self.name,
            provider_event_id=payload.source_ref,
            dedupe_key=(
                payload.idempotency_key
                or payload.source_ref
                or _payload_hash(validated_event.raw_payload)
            ),
            occurred_at=payload.captured_at,
            actor_ref=payload.actor_ref,
            payload=validated_event.raw_payload,
        )

    def to_raw_event_input(self, validated_event: ValidatedConnectorEvent) -> RawEventInput:
        return validated_event.raw_event

    def extract_drafts(self, raw_event: RawEvent) -> list[IdeaDraftInput]:
        payload = validate_manual_idea_payload(json.loads(raw_event.payload))
        return [
            IdeaDraftInput(
                text=payload.text,
                source_created_at=payload.captured_at,
                source_uri=payload.source_ref,
                metadata=payload.metadata,
                tags=payload.tags,
            )
        ]


def _payload_hash(raw_payload: str) -> str:
    return sha256(raw_payload.encode("utf-8")).hexdigest()


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
