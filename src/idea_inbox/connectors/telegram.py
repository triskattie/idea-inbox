"""Offline Telegram update parsing connector."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from idea_inbox.core.models import RawEvent
from idea_inbox.core.ports import IdeaDraftInput, RawEventInput, ValidatedConnectorEvent

_TELEGRAM_UPDATE_KINDS = ("message", "channel_post", "edited_message", "edited_channel_post")


class TelegramConnector:
    """Parse Telegram Bot API update payloads without network calls or SDK objects."""

    name = "telegram"
    source = "telegram"

    def parse_update(self, payload: dict[str, Any]) -> ValidatedConnectorEvent | None:
        """Return a validated connector event for a Telegram update fixture."""
        try:
            return self.validate(payload)
        except TelegramUpdateValidationError:
            return None

    def validate(
        self,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        credentials: object | None = None,
    ) -> ValidatedConnectorEvent:
        del headers, credentials
        update_id = _required_int(payload, "update_id")
        update_kind, message = _message_from_update(payload)
        message_id = _required_int(message, "message_id")
        chat = _required_mapping(message, "chat")
        chat_id = _required_int(chat, "id")
        chat_type = _required_str(chat, "type")
        occurred_at = _telegram_timestamp(message.get("date"))
        actor_ref = _actor_ref(message, chat)
        source_uri = f"telegram://chat/{chat_id}/message/{message_id}"
        metadata: dict[str, Any] = {
            "chat_id": chat_id,
            "chat_type": chat_type,
            "message_id": message_id,
            "update_id": update_id,
            "update_kind": update_kind,
        }
        if "edit_date" in message:
            metadata["edit_date"] = _telegram_timestamp(message.get("edit_date"))

        text = message.get("text")
        drafts: tuple[IdeaDraftInput, ...] = ()
        if isinstance(text, str) and text.strip():
            drafts = (
                IdeaDraftInput(
                    text=text.strip(),
                    source_created_at=occurred_at,
                    source_uri=source_uri,
                    metadata=metadata,
                ),
            )

        raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return ValidatedConnectorEvent(
            source=self.source,
            raw_event=self.to_raw_event_input(
                ValidatedConnectorEvent(
                    source=self.source,
                    raw_event=_raw_event_input(
                        source=self.source,
                        provider_event_id=str(update_id),
                        dedupe_key=str(update_id),
                        occurred_at=occurred_at,
                        actor_ref=actor_ref,
                        payload=raw_payload,
                    ),
                )
            ),
            drafts=drafts,
        )

    def to_raw_event_input(self, validated_event: ValidatedConnectorEvent) -> RawEventInput:
        return validated_event.raw_event

    def extract_drafts(self, raw_event: RawEvent) -> list[IdeaDraftInput]:
        event = self.validate(json.loads(raw_event.payload))
        return list(event.drafts)


class TelegramUpdateValidationError(ValueError):
    """Raised when a Telegram update fixture lacks required message fields."""


def _raw_event_input(
    *,
    source: str,
    provider_event_id: str | None,
    dedupe_key: str,
    occurred_at: str | None,
    actor_ref: str | None,
    payload: str,
) -> RawEventInput:
    return RawEventInput(
        source=source,
        provider_event_id=provider_event_id,
        dedupe_key=dedupe_key,
        occurred_at=occurred_at,
        actor_ref=actor_ref,
        payload=payload,
    )


def _message_from_update(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for update_kind in _TELEGRAM_UPDATE_KINDS:
        message = payload.get(update_kind)
        if isinstance(message, dict):
            return update_kind, message
    raise TelegramUpdateValidationError("Telegram update does not contain a supported message")


def _required_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise TelegramUpdateValidationError(f"Telegram field {key!r} must be an object")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TelegramUpdateValidationError(f"Telegram field {key!r} must be an integer")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TelegramUpdateValidationError(f"Telegram field {key!r} must be a non-empty string")
    return value


def _telegram_timestamp(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return (
        datetime.fromtimestamp(value, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _actor_ref(message: dict[str, Any], chat: dict[str, Any]) -> str:
    sender = message.get("from")
    if isinstance(sender, dict):
        sender_id = sender.get("id")
        if isinstance(sender_id, int) and not isinstance(sender_id, bool):
            return f"telegram:user:{sender_id}"
    chat_id = _required_int(chat, "id")
    return f"telegram:chat:{chat_id}"
