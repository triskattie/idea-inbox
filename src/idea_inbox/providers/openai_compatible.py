"""OpenAI-compatible chat/completions provider adapter boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any
from urllib import request as urllib_request

from idea_inbox.core.ports import CredentialProvider, CredentialRequest, ModelProviderOptions
from idea_inbox.core.query import NO_EVIDENCE_MESSAGE, AnswerEvidence, QueryAnswer
from idea_inbox.providers.mock import MockCredentialProvider

HttpPost = Callable[..., dict[str, Any]]

SYSTEM_PROMPT = "Answer only from the supplied stored idea evidence and keep claims citation-safe."


class OpenAICompatibleModelProvider:
    """Map citation-safe evidence to an OpenAI-compatible chat/completions request."""

    mode = "openai_compatible"
    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        credential_provider: CredentialProvider,
        credential_handle: str,
        http_post: HttpPost | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._credential_provider = credential_provider
        self._credential_handle = credential_handle
        self._http_post = http_post or _stdlib_http_post

    def answer(
        self,
        *,
        query: str,
        evidence: Sequence[AnswerEvidence],
        options: ModelProviderOptions | None = None,
    ) -> QueryAnswer:
        if not evidence:
            return QueryAnswer(message=NO_EVIDENCE_MESSAGE, grounding="no_relevant_stored_ideas")
        credential = self._credential_provider.resolve(
            CredentialRequest(handle=self._credential_handle, source="static_config")
        )
        if credential is None:
            credential = self._credential_provider.resolve(
                CredentialRequest(handle=self._credential_handle, source="env_api_key")
            )
        if credential is None:
            raise ValueError("OpenAI-compatible credential is missing.")

        headers = {
            "Authorization": f"Bearer {credential.value}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _prompt(query, evidence)},
            ],
            "stream": False,
        }
        if options is not None:
            if options.temperature is not None:
                body["temperature"] = options.temperature
            if options.max_output_tokens is not None:
                body["max_tokens"] = options.max_output_tokens

        response = self._http_post(
            f"{self._base_url}/chat/completions", headers=headers, payload=body
        )
        return QueryAnswer(message=_message_from_payload(response), grounding="stored_ideas")


def build_openai_compatible_model_provider(
    *,
    base_url: str,
    model: str,
    api_key: str,
    http_post: HttpPost | None = None,
) -> OpenAICompatibleModelProvider:
    """Construct an OpenAI-compatible provider from already-resolved config values."""
    return OpenAICompatibleModelProvider(
        base_url=base_url,
        model=model,
        credential_provider=MockCredentialProvider(static_credentials={"api-key": api_key}),
        credential_handle="api-key",
        http_post=http_post,
    )


def _prompt(query: str, evidence: Sequence[AnswerEvidence]) -> str:
    evidence_lines = "\n".join(
        f"[{index}] {item.idea_id}: {item.snippet}" for index, item in enumerate(evidence, start=1)
    )
    return f"Query: {query}\nEvidence:\n{evidence_lines}"


def _message_from_payload(payload: dict[str, Any]) -> str:
    try:
        message = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("OpenAI-compatible response did not include message content.") from exc
    if not isinstance(message, str) or not message.strip():
        raise ValueError("OpenAI-compatible response message content was empty.")
    return message.strip()


def _stdlib_http_post(
    url: str, *, headers: dict[str, str], payload: dict[str, Any]
) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib_request.Request(url, data=body, headers=headers, method="POST")
    with urllib_request.urlopen(req, timeout=30) as response:  # noqa: S310
        response_body = response.read().decode("utf-8")
    payload = json.loads(response_body)
    if not isinstance(payload, dict):
        raise ValueError("OpenAI-compatible response body must be a JSON object.")
    return payload
