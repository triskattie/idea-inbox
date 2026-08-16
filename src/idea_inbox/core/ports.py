"""SDK-free core protocols for storage and search adapters."""

from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Protocol

from idea_inbox.core.models import Idea, IdeaDraft, RawEvent, SearchHit


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

    def search(self, query: str, limit: int = 10) -> list[SearchHit]: ...

    def rebuild(self) -> None: ...
