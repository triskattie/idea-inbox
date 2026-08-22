"""Fixture-driven email connector adapter.

This module parses raw RFC 5322 messages only. It does not open IMAP sockets or read mailboxes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC
from email import message_from_string, policy
from email.message import EmailMessage, Message
from email.parser import BytesParser  # noqa: F401  (kept for future bytes-boundary use)
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

from idea_inbox.core.models import RawEvent
from idea_inbox.core.ports import IdeaDraftInput, RawEventInput, ValidatedConnectorEvent


class EmailConnectorError(ValueError):
    """Raised when a raw email fixture cannot be accepted by the email connector."""


@dataclass(frozen=True)
class ValidatedEmailMessage:
    raw_message: str
    message: EmailMessage | Message
    message_id: str
    sender: str | None
    subject: str | None
    occurred_at: str | None
    body_text: str


class EmailConnector:
    """Parse raw email fixtures into raw events and idea drafts without network access."""

    name = "email"

    def validate(
        self,
        payload: object,
        headers: dict[str, str] | None = None,
        credentials: object | None = None,
    ) -> ValidatedConnectorEvent:
        del headers, credentials
        validated = self._validate_message(payload)
        metadata: dict[str, Any] = {
            "message_id": validated.message_id,
            "from": validated.sender,
            "subject": validated.subject,
        }
        return ValidatedConnectorEvent(
            source=self.name,
            raw_event=RawEventInput(
                source=self.name,
                provider_event_id=validated.message_id,
                dedupe_key=validated.message_id,
                occurred_at=validated.occurred_at,
                actor_ref=validated.sender,
                payload=_raw_payload(validated),
            ),
            drafts=(
                IdeaDraftInput(
                    text=validated.body_text,
                    source_created_at=validated.occurred_at,
                    source_uri=f"email:{validated.message_id}",
                    metadata=metadata,
                ),
            ),
        )

    def _validate_message(self, payload: object) -> ValidatedEmailMessage:
        if not isinstance(payload, str) or not payload.strip():
            raise EmailConnectorError("Email connector payload must be a non-empty RFC 5322 string")

        message = message_from_string(payload, policy=policy.default)
        message_id = _header_value(message, "Message-ID")
        if not message_id:
            raise EmailConnectorError("Email Message-ID header is required for idempotency")

        body_text = _extract_body_text(message)
        if not body_text:
            raise EmailConnectorError("Email body must contain extractable text")

        return ValidatedEmailMessage(
            raw_message=payload,
            message=message,
            message_id=message_id,
            sender=_header_value(message, "From"),
            subject=_header_value(message, "Subject"),
            occurred_at=_date_header_to_utc(message, "Date"),
            body_text=body_text,
        )

    def to_raw_event_input(self, validated_event: ValidatedConnectorEvent) -> RawEventInput:
        return validated_event.raw_event

    def extract_drafts(self, raw_event: RawEvent) -> list[IdeaDraftInput]:
        event = self.validate(json.loads(raw_event.payload)["raw_message"])
        return list(event.drafts)


def _raw_payload(event: ValidatedEmailMessage) -> str:
    return json.dumps(
        {
            "message_id": event.message_id,
            "from": event.sender,
            "subject": event.subject,
            "date": event.occurred_at,
            "body_text": event.body_text,
            "raw_message": event.raw_message,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _header_value(message: EmailMessage | Message, name: str) -> str | None:
    value = message.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_header_to_utc(message: EmailMessage | Message, name: str) -> str | None:
    value = _header_value(message, name)
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_body_text(message: EmailMessage | Message) -> str:
    plain = _message_part_text(message, "text/plain")
    if plain is not None:
        return _normalize_text(plain)

    html = _message_part_text(message, "text/html")
    if html is not None:
        return _normalize_text(_html_to_text(html))

    return ""


def _normalize_text(text: str) -> str:
    collapsed = " ".join(text.split())
    return collapsed.strip()


def _message_part_text(message: EmailMessage | Message, content_type: str) -> str | None:
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart() or part.get_content_type() != content_type:
                continue
            content = _part_content(part)
            if content and content.strip():
                return content
        return None

    if message.get_content_type() != content_type:
        return None
    return _part_content(message)


def _part_content(part: EmailMessage | Message) -> str | None:
    try:
        content = part.get_content()
    except (AttributeError, LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True)
        if payload is None:
            return None
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return content if isinstance(content, str) else None


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(self.parts)


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()
