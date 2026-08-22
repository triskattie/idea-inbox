"""Deterministic offline provider adapters for tests and local harnesses."""

from collections.abc import Mapping, Sequence

from idea_inbox.core.ports import (
    CredentialMaterial,
    CredentialProvider,
    CredentialRequest,
    ModelProviderOptions,
)
from idea_inbox.core.query import NO_EVIDENCE_MESSAGE, AnswerEvidence, QueryAnswer


class MockCredentialProvider:
    """Resolve no-secret, env, and static credentials without external services."""

    def __init__(
        self,
        *,
        static_credentials: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._static_credentials = dict(static_credentials or {})
        self._env = dict(env or {})

    def resolve(self, request: CredentialRequest) -> CredentialMaterial | None:
        if request.source == "none":
            return CredentialMaterial(value="", scheme="none", secret=False)
        if request.source == "static_config":
            value = self._static_credentials.get(request.handle, "")
        elif request.source == "env_api_key":
            value = self._env.get(request.handle, "")
        else:
            return None
        if not value:
            return None
        return CredentialMaterial(value=value, scheme="bearer", secret=True)


class MockModelProvider:
    """Deterministic model provider that preserves the v0.2 query contract."""

    mode = "deterministic_mock"

    def __init__(self, provider_name: str = "mock") -> None:
        self.provider_name = provider_name

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


class MockEmbeddingProvider:
    """Deterministic embedding placeholder; does not enable vector search."""

    provider_name = "mock"

    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            seed = sum(ord(character) for character in text) % 1000
            vectors.append(
                [
                    round(((seed * (index + 1)) % 1000) / 1000, 3)
                    for index in range(self._dimensions)
                ]
            )
        return vectors


__all__ = [
    "CredentialProvider",
    "MockCredentialProvider",
    "MockEmbeddingProvider",
    "MockModelProvider",
]
