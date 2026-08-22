"""SDK-free core protocols for storage, search, and provider adapters."""

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable

from idea_inbox.core.models import Idea, IdeaDraft, RawEvent, SearchHit


@dataclass(frozen=True)
class RawEventInput:
    """Connector-built raw event fields before core assigns internal IDs."""

    source: str
    provider_event_id: str | None
    dedupe_key: str
    occurred_at: str | None
    actor_ref: str | None
    payload: str

    def payload_hash(self) -> str:
        return sha256(self.payload.encode("utf-8")).hexdigest()

    def to_raw_event(self, *, raw_event_id: str, received_at: str) -> RawEvent:
        return RawEvent(
            id=raw_event_id,
            source=self.source,
            provider_event_id=self.provider_event_id,
            dedupe_key=self.dedupe_key,
            received_at=received_at,
            occurred_at=self.occurred_at,
            actor_ref=self.actor_ref,
            payload=self.payload,
            payload_hash=self.payload_hash(),
            processing_state="pending",
        )


@dataclass(frozen=True)
class IdeaDraftInput:
    """Connector-extracted idea candidate before core assigns an internal ID."""

    text: str
    source_created_at: str | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] | None = None
    tags: tuple[str, ...] = ()

    def to_idea_draft(self, raw_event_id: str, *, draft_id: str) -> IdeaDraft:
        return IdeaDraft(
            id=draft_id,
            raw_event_id=raw_event_id,
            text=self.text,
            source_created_at=self.source_created_at,
            source_uri=self.source_uri,
            metadata=self.metadata or {},
            extraction_state="accepted",
        )


@dataclass(frozen=True)
class ValidatedConnectorEvent:
    """SDK-free validated connector payload ready for shared ingestion."""

    source: str
    raw_event: RawEventInput
    drafts: tuple[IdeaDraftInput, ...] = ()


@runtime_checkable
class Connector(Protocol):
    """SDK-free adapter boundary for optional external event sources.

    Adapters validate untrusted payloads at the boundary, build one persisted
    raw event input per incoming event, and extract zero or more idea drafts
    from a stored raw event. Provider SDK types must not leak through this
    contract.
    """

    name: str

    def validate(
        self,
        payload: Any,
        headers: dict[str, str] | None = None,
        credentials: Any | None = None,
    ) -> ValidatedConnectorEvent: ...

    def to_raw_event_input(self, validated_event: ValidatedConnectorEvent) -> RawEventInput: ...

    def extract_drafts(self, raw_event: RawEvent) -> list[IdeaDraftInput]: ...


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

    def answer(
        self,
        *,
        query: str,
        evidence: Sequence[Any],
        options: "ModelProviderOptions | None" = None,
    ) -> Any: ...


@dataclass(frozen=True)
class ModelProviderOptions:
    """Provider-neutral generation options for retrieval-grounded answers."""

    temperature: float | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True)
class CredentialRequest:
    """SDK-free credential lookup request owned by provider adapters."""

    handle: str
    source: str


@dataclass(frozen=True)
class CredentialMaterial:
    """Resolved request auth data without provider SDK credential objects."""

    value: str
    scheme: str = "bearer"
    secret: bool = True


class CredentialProvider(Protocol):
    """Resolve credentials for model or embedding providers without SDK leakage."""

    def resolve(self, request: CredentialRequest) -> CredentialMaterial | None: ...


class EmbeddingProvider(Protocol):
    """Future embedding provider contract; vector search is not enabled by this shape."""

    provider_name: str

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


ModelProvider = Answerer


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
