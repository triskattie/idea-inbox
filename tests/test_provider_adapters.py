from __future__ import annotations

from typing import Any

from idea_inbox.core.ports import CredentialRequest, ModelProviderOptions
from idea_inbox.core.query import AnswerEvidence
from idea_inbox.providers.mock import (
    MockCredentialProvider,
    MockEmbeddingProvider,
    MockModelProvider,
)
from idea_inbox.providers.ollama import OllamaModelProvider
from idea_inbox.providers.openai_compatible import OpenAICompatibleModelProvider

SYSTEM_PROMPT = "Answer only from the supplied stored idea evidence and keep claims citation-safe."
USER_PROMPT = (
    "Query: What did I save about local AI?\n"
    "Evidence:\n"
    "[1] idea_local_ai: Prototype local-first capture before connector work."
)
OLLAMA_PROMPT = (
    "Answer only from stored idea evidence.\n\n"
    "Query: What did I save about local AI?\n"
    "Evidence:\n"
    "[1] idea_local_ai: Prototype local-first capture before connector work."
)


def evidence(text: str = "Prototype local-first capture before connector work.") -> AnswerEvidence:
    return AnswerEvidence(
        idea_id="idea_local_ai",
        text=text,
        snippet=text,
        source="manual",
        source_ref="manual-note-1",
        captured_at="2026-08-08T00:00:00Z",
        raw_event_id="raw_local_ai",
        draft_id="draft_local_ai",
        rank=1,
        score=-1.0,
    )


def test_mock_model_and_credential_providers_are_deterministic_and_offline() -> None:
    credential_provider = MockCredentialProvider(
        static_credentials={"mock-token": "secret-value"},
        env={"IDEA_INBOX_OPENAI_API_KEY": "env-secret"},
    )
    model_provider = MockModelProvider()
    embedding_provider = MockEmbeddingProvider(dimensions=4)

    static_credential = credential_provider.resolve(
        CredentialRequest(handle="mock-token", source="static_config")
    )
    env_credential = credential_provider.resolve(
        CredentialRequest(handle="IDEA_INBOX_OPENAI_API_KEY", source="env_api_key")
    )
    none_credential = credential_provider.resolve(CredentialRequest(handle="local", source="none"))
    answer = model_provider.answer(
        query="What did I save about local AI?",
        evidence=[evidence()],
        options=ModelProviderOptions(temperature=0.2, max_output_tokens=128),
    )
    no_evidence_answer = model_provider.answer(query="Mars colony", evidence=[])

    assert static_credential is not None
    assert static_credential.secret is True
    assert static_credential.value == "secret-value"
    assert env_credential is not None
    assert env_credential.value == "env-secret"
    assert none_credential is not None
    assert none_credential.value == ""
    assert answer.grounding == "stored_ideas"
    assert "Prototype local-first capture" in answer.message
    assert no_evidence_answer.grounding == "no_relevant_stored_ideas"
    assert embedding_provider.embed_texts(["local AI", "garden"]) == [
        [0.693, 0.386, 0.079, 0.772],
        [0.625, 0.25, 0.875, 0.5],
    ]


def test_openai_compatible_adapter_maps_evidence_to_chat_completion_without_network() -> None:
    calls: list[dict[str, Any]] = []

    def fake_http_post(
        url: str, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        calls.append({"url": url, "headers": headers, "json": payload})
        return {
            "choices": [{"message": {"content": "You saved an idea about local-first capture."}}]
        }

    provider = OpenAICompatibleModelProvider(
        base_url="https://llm.example.test/v1",
        model="test-chat-model",
        credential_provider=MockCredentialProvider(static_credentials={"openai-key": "token-123"}),
        credential_handle="openai-key",
        http_post=fake_http_post,
    )

    answer = provider.answer(query="What did I save about local AI?", evidence=[evidence()])

    assert answer.message == "You saved an idea about local-first capture."
    assert answer.grounding == "stored_ideas"
    assert calls == [
        {
            "url": "https://llm.example.test/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer token-123",
                "Content-Type": "application/json",
            },
            "json": {
                "model": "test-chat-model",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT},
                ],
                "stream": False,
            },
        }
    ]


def test_ollama_adapter_maps_evidence_to_local_generate_without_secret() -> None:
    calls: list[dict[str, Any]] = []

    def fake_http_post(
        url: str, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        calls.append({"url": url, "headers": headers, "json": payload})
        return {"response": "You saved an idea about local-first capture."}

    provider = OllamaModelProvider(
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        credential_provider=MockCredentialProvider(),
        http_post=fake_http_post,
    )

    answer = provider.answer(query="What did I save about local AI?", evidence=[evidence()])

    assert answer.message == "You saved an idea about local-first capture."
    assert answer.grounding == "stored_ideas"
    assert calls == [
        {
            "url": "http://127.0.0.1:11434/api/generate",
            "headers": {"Content-Type": "application/json"},
            "json": {
                "model": "llama3.2",
                "prompt": OLLAMA_PROMPT,
                "stream": False,
            },
        }
    ]
