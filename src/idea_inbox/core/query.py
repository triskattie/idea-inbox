"""SDK-free cited-query orchestration and deterministic answer generation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from idea_inbox.core.models import Idea, SearchHit, SearchLimitError
from idea_inbox.core.ports import Answerer, ModelProviderOptions, SearchIndex, StorageBackend

NO_EVIDENCE_MESSAGE = "I could not find relevant stored ideas for that query."
DETERMINISTIC_ANSWER_MODE = "deterministic_mock"
MAX_QUERY_LIMIT = 50

_QUERY_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)
_QUERY_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "did",
        "do",
        "does",
        "for",
        "i",
        "me",
        "my",
        "of",
        "save",
        "saved",
        "the",
        "what",
    }
)


class QueryValidationError(ValueError):
    """Raised when a cited-query request violates the public API contract."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


@dataclass(frozen=True)
class QueryRequest:
    """Validated cited-query request independent from HTTP transport details."""

    query: str
    limit: int = 10
    filters: dict[str, str] | None = None
    include_hits: bool = True


@dataclass(frozen=True)
class AnswerEvidence:
    """Safe stored-idea evidence passed to answerers.

    Provider adapters must depend on this SDK-free shape rather than storage rows,
    search-index rows, provider SDK objects, or credential handles. It contains only retrieved
    idea text plus citation-safe metadata, so hosted, OAuth/proxy, and local provider adapters
    can be swapped in later without changing core query orchestration.
    """

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


@dataclass(frozen=True)
class QueryAnswer:
    """Answer text produced by an SDK-free answerer implementation."""

    message: str
    grounding: str


@dataclass(frozen=True)
class QueryResult:
    """Transport-independent cited-query response model."""

    answer: QueryAnswer
    citations: list[dict[str, Any]]
    hits: list[dict[str, Any]]
    meta: dict[str, Any]


class DeterministicMockAnswerer:
    """Local deterministic answerer for tests and release-readiness smoke.

    This answerer performs no network or model calls and receives only resolved evidence supplied by
    query orchestration. Real hosted, proxy/OAuth, or local model adapters should implement the same
    ``Answerer`` protocol in adapter modules outside core.
    """

    mode = DETERMINISTIC_ANSWER_MODE
    provider_name = "mock"

    def answer(
        self,
        *,
        query: str,
        evidence: Sequence[AnswerEvidence],
        options: ModelProviderOptions | None = None,
    ) -> QueryAnswer:
        if not evidence:
            return QueryAnswer(message=NO_EVIDENCE_MESSAGE, grounding="no_relevant_stored_ideas")
        first = evidence[0]
        return QueryAnswer(
            message=f"You saved an idea: {first.text}",
            grounding="stored_ideas",
        )


def validate_query_request(body: Any) -> QueryRequest:
    """Validate a JSON-like request body for the cited-query service."""
    if not isinstance(body, dict):
        raise QueryValidationError("Request body must be a JSON object.", "body")

    query_value = body.get("query")
    if not isinstance(query_value, str):
        raise QueryValidationError("Query must be a string.", "query")
    query = query_value.strip()
    if not query:
        raise QueryValidationError("Query must not be empty.", "query")
    if len(query) > 2000:
        raise QueryValidationError("Query must be at most 2000 characters.", "query")

    limit_value = body.get("limit", 10)
    if not isinstance(limit_value, int) or isinstance(limit_value, bool):
        raise QueryValidationError(f"Query limit must be between 1 and {MAX_QUERY_LIMIT}.", "limit")
    if not 1 <= limit_value <= MAX_QUERY_LIMIT:
        raise SearchLimitError(f"query limit must be between 1 and {MAX_QUERY_LIMIT}")

    include_hits_value = body.get("include_hits", True)
    if not isinstance(include_hits_value, bool):
        raise QueryValidationError("include_hits must be a boolean.", "include_hits")

    filters = _validate_filters(body.get("filters", {}))
    return QueryRequest(
        query=query,
        limit=limit_value,
        filters=filters,
        include_hits=include_hits_value,
    )


def answer_query(
    *,
    storage: StorageBackend,
    search_index: SearchIndex,
    request: QueryRequest,
    answerer: Answerer | None = None,
) -> QueryResult:
    """Retrieve stored evidence, resolve citations through storage, and answer deterministically."""
    answerer = answerer or DeterministicMockAnswerer()
    hits = _search_with_salient_fallback(search_index, request)
    evidence = _resolve_evidence(storage, hits, request.query)
    answer = answerer.answer(query=request.query, evidence=evidence)
    grounding = answer.grounding
    citations = _citations(evidence) if grounding == "stored_ideas" else []
    visible_hits = _hits(evidence) if request.include_hits and evidence else []
    meta: dict[str, Any] = {
        "query": request.query,
        "limit": request.limit,
        "grounding": grounding,
        "answer_mode": getattr(answerer, "mode", DETERMINISTIC_ANSWER_MODE),
        "retrieval": {"strategy": "sqlite_fts", "evidence_count": len(evidence)},
    }
    provider_name = getattr(answerer, "provider_name", None)
    if provider_name is not None and evidence:
        meta["model_provider"] = provider_name
    return QueryResult(answer=answer, citations=citations, hits=visible_hits, meta=meta)


def _validate_filters(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise QueryValidationError("filters must be an object.", "filters")
    unknown = set(value) - {"source"}
    if unknown:
        field = f"filters.{sorted(unknown)[0]}"
        raise QueryValidationError("Unknown query filter.", field)
    source = value.get("source")
    if source is None:
        return {}
    if not isinstance(source, str) or not source.strip():
        raise QueryValidationError("filters.source must be a non-empty string.", "filters.source")
    return {"source": source.strip()}


def _search_with_salient_fallback(
    search_index: SearchIndex, request: QueryRequest
) -> list[SearchHit]:
    hits = search_index.search(request.query, limit=request.limit, filters=request.filters)
    if hits:
        return hits
    salient_query = _salient_query(request.query)
    if salient_query == request.query:
        return hits
    return search_index.search(salient_query, limit=request.limit, filters=request.filters)


def _salient_query(query: str) -> str:
    tokens = _QUERY_TOKEN_PATTERN.findall(query)
    salient = [token for token in tokens if token.casefold() not in _QUERY_STOPWORDS]
    return " ".join(salient) if salient else query


def _resolve_evidence(
    storage: StorageBackend, hits: list[SearchHit], query: str
) -> list[AnswerEvidence]:
    evidence: list[AnswerEvidence] = []
    salient_tokens = [token.casefold() for token in _salient_query(query).split()]
    for hit in hits:
        idea = storage.get_idea(hit.idea_id)
        if idea is None or not _matches_salient_token(idea.text, salient_tokens):
            continue
        evidence.append(_evidence_from_idea(idea, hit, rank=len(evidence) + 1))
    return evidence


def _matches_salient_token(text: str, salient_tokens: list[str]) -> bool:
    if not salient_tokens:
        return True
    text_casefold = text.casefold()
    return any(token in text_casefold for token in salient_tokens)


def _evidence_from_idea(idea: Idea, hit: SearchHit, *, rank: int) -> AnswerEvidence:
    return AnswerEvidence(
        idea_id=idea.id,
        text=idea.text,
        snippet=idea.text,
        source=idea.source,
        source_ref=idea.source_ref,
        captured_at=idea.captured_at,
        raw_event_id=idea.raw_event_id,
        draft_id=idea.draft_id,
        rank=rank,
        score=hit.score,
    )


def _citations(evidence: list[AnswerEvidence]) -> list[dict[str, Any]]:
    return [
        {
            "citation_id": f"c{index}",
            "idea_id": item.idea_id,
            "snippet": item.snippet,
            "source": item.source,
            "source_ref": item.source_ref,
            "captured_at": item.captured_at,
            "provenance": {"raw_event_id": item.raw_event_id, "draft_id": item.draft_id},
        }
        for index, item in enumerate(evidence, start=1)
    ]


def _hits(evidence: list[AnswerEvidence]) -> list[dict[str, Any]]:
    return [
        {
            "idea_id": item.idea_id,
            "rank": item.rank,
            "score": item.score,
            "snippet": item.snippet,
            "source": item.source,
            "captured_at": item.captured_at,
        }
        for item in evidence
    ]
