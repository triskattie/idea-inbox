"""Reusable validation for manual idea capture payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from idea_inbox.core.models import IdeaInboxError

MAX_IDENTITY_LENGTH = 512
MAX_TAG_LENGTH = 64
MAX_TAGS = 50
MAX_TEXT_LENGTH = 10_000


class ManualIdeaValidationError(IdeaInboxError, ValueError):
    """Raised when a manual idea payload fails boundary validation."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


@dataclass(frozen=True)
class ManualIdeaPayload:
    """Normalized manual idea payload accepted by API and server actions."""

    text: str
    source_ref: str | None = None
    actor_ref: str | None = None
    captured_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


def validate_manual_idea_payload(body: Any) -> ManualIdeaPayload:
    """Validate and normalize an untrusted manual idea request body."""
    if not isinstance(body, dict):
        raise ManualIdeaValidationError("Request body must be a JSON object.", "body")

    raw_text = body.get("text")
    if not isinstance(raw_text, str):
        raise ManualIdeaValidationError("Idea text must not be empty.", "text")
    text = raw_text.strip()
    if not text:
        raise ManualIdeaValidationError("Idea text must not be empty.", "text")
    if len(text) > MAX_TEXT_LENGTH:
        raise ManualIdeaValidationError(
            f"Idea text must be {MAX_TEXT_LENGTH} characters or fewer.", "text"
        )

    metadata = body.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ManualIdeaValidationError("Idea metadata must be a JSON object.", "metadata")

    return ManualIdeaPayload(
        text=text,
        source_ref=_optional_string(body, "source_ref"),
        actor_ref=_optional_string(body, "actor_ref"),
        captured_at=_optional_string(body, "captured_at"),
        metadata=dict(metadata),
        tags=_normalize_tags(body.get("tags", [])),
    )


def _optional_string(body: dict[str, Any], field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManualIdeaValidationError(f"Idea {field} must be a string.", field)
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > MAX_IDENTITY_LENGTH:
        raise ManualIdeaValidationError(
            f"Idea {field} must be {MAX_IDENTITY_LENGTH} characters or fewer.", field
        )
    return normalized


def _normalize_tags(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ManualIdeaValidationError("Idea tags must be a list of strings.", "tags")
    if len(value) > MAX_TAGS:
        raise ManualIdeaValidationError(
            f"Idea tags must include {MAX_TAGS} items or fewer.", "tags"
        )

    normalized_tags: list[str] = []
    for tag in value:
        if not isinstance(tag, str):
            raise ManualIdeaValidationError("Idea tags must be a list of strings.", "tags")
        normalized = tag.strip().lower()
        if not normalized:
            continue
        if len(normalized) > MAX_TAG_LENGTH:
            raise ManualIdeaValidationError(
                f"Idea tags must be {MAX_TAG_LENGTH} characters or fewer.", "tags"
            )
        normalized_tags.append(normalized)

    return tuple(dict.fromkeys(normalized_tags))
