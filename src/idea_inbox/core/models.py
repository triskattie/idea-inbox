"""SDK-free domain models for Idea Inbox."""

from dataclasses import dataclass, field
from typing import Any


class IdeaInboxError(Exception):
    """Base exception for domain-level Idea Inbox errors."""


class EmptySearchQuery(IdeaInboxError, ValueError):
    """Raised when a search query is empty after normalization."""


class SearchLimitError(IdeaInboxError, ValueError):
    """Raised when a search limit is outside supported bounds."""


@dataclass(frozen=True)
class RawEvent:
    id: str
    source: str
    provider_event_id: str | None
    dedupe_key: str
    received_at: str
    occurred_at: str | None
    actor_ref: str | None
    payload: str
    payload_hash: str
    processing_state: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class IdeaDraft:
    id: str
    raw_event_id: str
    text: str
    source_created_at: str | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_state: str = "pending"


@dataclass(frozen=True)
class Idea:
    id: str
    raw_event_id: str
    text: str
    source: str
    source_ref: str | None
    captured_at: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    embedding_state: str = "not_requested"
    draft_id: str | None = None


@dataclass(frozen=True)
class SearchHit:
    idea_id: str
    text: str
    score: float
    rank: int
    source: str
    captured_at: str
    snippet: str


@dataclass(frozen=True)
class Citation:
    idea_id: str
    quote: str
    source: str
    captured_at: str
