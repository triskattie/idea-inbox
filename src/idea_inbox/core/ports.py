"""SDK-free core protocols for storage and search adapters."""

from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Protocol

from idea_inbox.core.models import Idea, RawEvent, SearchHit


class StorageBackend(Protocol):
    """Authoritative persistence contract for raw events and ideas."""

    def migrate(self) -> None: ...

    def save_raw_event(self, raw_event: RawEvent) -> RawEvent: ...

    def get_raw_event(self, raw_event_id: str) -> RawEvent | None: ...

    def save_idea(self, idea: Idea) -> Idea: ...

    def get_idea(self, idea_id: str) -> Idea | None: ...

    def delete_idea(self, idea_id: str) -> None: ...

    def transaction(self) -> AbstractContextManager[Iterator[None]]: ...


class SearchIndex(Protocol):
    """Derived search projection contract returning stored idea identifiers."""

    def upsert_idea(self, idea: Idea) -> None: ...

    def delete_idea(self, idea_id: str) -> None: ...

    def search(self, query: str, limit: int = 10) -> list[SearchHit]: ...

    def rebuild(self) -> None: ...
