"""SDK-free core protocols for storage and search adapters."""

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from typing import Any, Protocol

from idea_inbox.core.models import Idea, IdeaDraft, RawEvent, SearchHit


class AnswerEvidence(Protocol):
    """Citation-safe evidence shape accepted by answerer adapters."""

    idea_id: str
    text: str
    snippet: str
    source: str
    source_ref: str | None
    captured_at: str
    raw_event_id: str | None
    draft_id: str | None
    rank: int
    score: float


class QueryAnswer(Protocol):
    """SDK-free answer text returned by hosted, proxy/OAuth, local, or mock answerers."""

    message: str
    grounding: str


class Answerer(Protocol):
    """Replaceable answer-generation boundary for cited query.

    Implementations receive only resolved stored-idea evidence and return plain answer text. Adapter
    modules may wrap hosted, OAuth/proxy, or local credentials later, but core domain code must only
    depend on this protocol and never on provider SDK objects or API-key-specific configuration.
    """

    mode: str
    provider_name: str | None

    def answer(self, evidence: Sequence[AnswerEvidence]) -> QueryAnswer: ...


class StorageBackend(Protocol):
    """Authoritative persistence contract for raw events and ideas."""

    def migrate(self) -> None: ...

    def save_raw_event(self, raw_event: RawEvent) -> RawEvent: ...

    def get_raw_event(self, raw_event_id: str) -> RawEvent | None: ...

    def list_raw_events(
        self, *, processing_state: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[RawEvent]: ...

    def update_raw_event_processing_state(
        self,
        raw_event_id: str,
        processing_state: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> RawEvent | None: ...

    def save_idea_draft(self, idea_draft: IdeaDraft) -> IdeaDraft: ...

    def get_idea_draft(self, idea_draft_id: str) -> IdeaDraft | None: ...

    def list_idea_drafts(
        self, *, raw_event_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[IdeaDraft]: ...

    def save_idea(self, idea: Idea) -> Idea: ...

    def get_idea(self, idea_id: str) -> Idea | None: ...

    def list_ideas(
        self, *, raw_event_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Idea]: ...

    def delete_idea(self, idea_id: str) -> None: ...

    def transaction(self) -> AbstractContextManager[Iterator[None]]: ...


class SearchIndex(Protocol):
    """Derived search projection contract returning stored idea identifiers."""

    def upsert_idea(self, idea: Idea) -> None: ...

    def delete_idea(self, idea_id: str) -> None: ...

    def search(
        self, query: str, limit: int = 10, filters: dict[str, Any] | None = None
    ) -> list[SearchHit]: ...

    def rebuild(self) -> None: ...
