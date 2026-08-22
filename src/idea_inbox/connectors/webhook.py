"""Generic webhook connector adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from idea_inbox.core.manual_capture import ManualIdeaValidationError
from idea_inbox.core.models import RawEvent
from idea_inbox.core.ports import IdeaDraftInput, RawEventInput, ValidatedConnectorEvent


@dataclass(frozen=True)
class GenericWebhookEvent:
    text: str
    raw_payload: str
    event_id: str | None = None
    source_ref: str | None = None
    actor_ref: str | None = None
    occurred_at: str | None = None
    metadata: dict[str, Any] | None = None
    tags: tuple[str, ...] = ()


class GenericWebhookConnector:
    """Connector for source-agnostic JSON webhook idea events."""

    name = "webhook"

    def validate(
        self,
        payload: Any,
        headers: dict[str, str] | None = None,
        credentials: Any | None = None,
    ) -> ValidatedConnectorEvent:
        del headers, credentials
        if not isinstance(payload, dict):
            raise ManualIdeaValidationError("Webhook body must be a JSON object.", "body")
        text = _required_text(payload.get("text"))
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ManualIdeaValidationError("Webhook metadata must be a JSON object.", "metadata")
        event_id = _optional_string(payload, "event_id", preserve=True)
        validated = GenericWebhookEvent(
            text=text,
            event_id=event_id,
            source_ref=_optional_string(payload, "source_ref"),
            actor_ref=_optional_string(payload, "actor_ref"),
            occurred_at=_optional_string(payload, "occurred_at"),
            metadata=dict(metadata),
            tags=_normalize_tags(payload.get("tags", [])),
            raw_payload=json.dumps(payload, separators=(",", ":"), sort_keys=True),
        )
        return ValidatedConnectorEvent(
            source=self.name,
            raw_event=self.to_raw_event_input_payload(validated),
            drafts=(
                IdeaDraftInput(
                    text=validated.text,
                    source_created_at=validated.occurred_at,
                    source_uri=validated.source_ref,
                    metadata=validated.metadata or {},
                    tags=validated.tags,
                ),
            ),
        )

    def to_raw_event_input_payload(self, event: GenericWebhookEvent) -> RawEventInput:
        return RawEventInput(
            source=self.name,
            provider_event_id=event.event_id,
            dedupe_key=event.event_id or _payload_hash(event.raw_payload),
            occurred_at=event.occurred_at,
            actor_ref=event.actor_ref,
            payload=event.raw_payload,
        )

    def to_raw_event_input(self, validated_event: ValidatedConnectorEvent) -> RawEventInput:
        return validated_event.raw_event

    def extract_drafts(self, raw_event: RawEvent) -> list[IdeaDraftInput]:
        payload = self.validate(json.loads(raw_event.payload))
        return list(payload.drafts)


def _payload_hash(raw_payload: str) -> str:
    from hashlib import sha256

    return sha256(raw_payload.encode("utf-8")).hexdigest()


def _required_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ManualIdeaValidationError("Webhook text must not be empty.", "text")
    text = value.strip()
    if not text:
        raise ManualIdeaValidationError("Webhook text must not be empty.", "text")
    return text


def _optional_string(body: dict[str, Any], field: str, *, preserve: bool = False) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManualIdeaValidationError(f"Webhook {field} must be a string.", field)
    normalized = value if preserve else value.strip()
    if not normalized:
        return None
    return normalized


def _normalize_tags(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ManualIdeaValidationError("Webhook tags must be a list of strings.", "tags")
    normalized_tags: list[str] = []
    for tag in value:
        if not isinstance(tag, str):
            raise ManualIdeaValidationError("Webhook tags must be a list of strings.", "tags")
        normalized = tag.strip().lower()
        if normalized:
            normalized_tags.append(normalized)
    return tuple(dict.fromkeys(normalized_tags))
