"""Offline Discord gateway payload adapter."""

from __future__ import annotations

import json
from typing import Any

from idea_inbox.core.models import RawEvent
from idea_inbox.core.ports import IdeaDraftInput, RawEventInput, ValidatedConnectorEvent


class DiscordConnectorError(ValueError):
    """Raised when a Discord gateway payload cannot be accepted."""


class DiscordConnector:
    """Convert Discord gateway message payloads into core raw events and drafts."""

    name = "discord"

    def validate(
        self,
        payload: object,
        headers: dict[str, str] | None = None,
        credentials: object | None = None,
    ) -> ValidatedConnectorEvent:
        del headers, credentials
        if not isinstance(payload, dict):
            raise DiscordConnectorError("Discord payload must be a JSON object")
        if payload.get("t") != "MESSAGE_CREATE":
            raise DiscordConnectorError("Discord payload must be a MESSAGE_CREATE event")
        message = payload.get("d")
        if not isinstance(message, dict):
            raise DiscordConnectorError("Discord payload must include message data")
        for field in ("id", "channel_id", "timestamp"):
            if not isinstance(message.get(field), str) or not message[field].strip():
                raise DiscordConnectorError(f"Discord message data must include {field}")
        content = message.get("content", "")
        attachments = message.get("attachments", [])
        if not isinstance(content, str):
            raise DiscordConnectorError("Discord message content must be a string")
        if not isinstance(attachments, list):
            raise DiscordConnectorError("Discord message attachments must be a list")
        if not content.strip() and not attachments:
            raise DiscordConnectorError("Discord message must include content or attachments")
        author = message.get("author")
        if author is not None and not isinstance(author, dict):
            raise DiscordConnectorError("Discord message author must be an object when provided")

        raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        text = _draft_text(message)
        drafts: tuple[IdeaDraftInput, ...] = ()
        if text:
            drafts = (
                IdeaDraftInput(
                    text=text,
                    source_created_at=message.get("timestamp"),
                    source_uri=_source_uri(message),
                    metadata=_metadata(message),
                ),
            )
        return ValidatedConnectorEvent(
            source=self.name,
            raw_event=RawEventInput(
                source=self.name,
                provider_event_id=message["id"],
                dedupe_key=message["id"],
                occurred_at=message.get("timestamp"),
                actor_ref=_actor_ref(message),
                payload=raw_payload,
            ),
            drafts=drafts,
        )

    def to_raw_event_input(self, validated_event: ValidatedConnectorEvent) -> RawEventInput:
        return validated_event.raw_event

    def extract_drafts(self, raw_event: RawEvent) -> list[IdeaDraftInput]:
        event = self.validate(json.loads(raw_event.payload))
        return list(event.drafts)


def _actor_ref(message: dict[str, Any]) -> str | None:
    author = message.get("author")
    if not isinstance(author, dict):
        return None
    author_id = author.get("id")
    if not isinstance(author_id, str) or not author_id.strip():
        return None
    return f"discord:user:{author_id}"


def _source_uri(message: dict[str, Any]) -> str:
    guild_id = message.get("guild_id")
    channel_id = message["channel_id"]
    message_id = message["id"]
    if isinstance(guild_id, str) and guild_id:
        return f"discord://guilds/{guild_id}/channels/{channel_id}/messages/{message_id}"
    return f"discord://channels/{channel_id}/messages/{message_id}"


def _draft_text(message: dict[str, Any]) -> str:
    content = message.get("content", "").strip()
    if content:
        return content
    attachments = message.get("attachments", [])
    attachment_texts = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        filename = attachment.get("filename")
        url = attachment.get("url")
        if isinstance(filename, str) and filename and isinstance(url, str) and url:
            attachment_texts.append(f"Attachment: {filename} ({url})")
        elif isinstance(filename, str) and filename:
            attachment_texts.append(f"Attachment: {filename}")
    return "\n".join(attachment_texts)


def _metadata(message: dict[str, Any]) -> dict[str, Any]:
    author_value = message.get("author")
    author = author_value if isinstance(author_value, dict) else {}
    attachments = [
        {
            "id": attachment.get("id"),
            "filename": attachment.get("filename"),
            "url": attachment.get("url"),
            "content_type": attachment.get("content_type"),
            "size": attachment.get("size"),
        }
        for attachment in message.get("attachments", [])
        if isinstance(attachment, dict)
    ]
    return {
        "message_id": message["id"],
        "channel_id": message["channel_id"],
        "guild_id": message.get("guild_id"),
        "author_id": author.get("id"),
        "author_username": author.get("username"),
        "edited_timestamp": message.get("edited_timestamp"),
        "attachment_count": len(attachments),
        "attachments": attachments,
    }


__all__ = ["DiscordConnector", "DiscordConnectorError"]
