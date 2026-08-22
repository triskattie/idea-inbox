"""Local Ollama provider adapter boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any
from urllib import request as urllib_request

from idea_inbox.core.ports import CredentialProvider, CredentialRequest, ModelProviderOptions
from idea_inbox.core.query import NO_EVIDENCE_MESSAGE, AnswerEvidence, QueryAnswer

HttpPost = Callable[..., dict[str, Any]]


class OllamaModelProvider:
    """Map citation-safe evidence to the local Ollama generate API."""

    mode = "ollama"
    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        credential_provider: CredentialProvider,
        http_post: HttpPost | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._credential_provider = credential_provider
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
            CredentialRequest(handle="local", source="none")
        )
        headers = {"Content-Type": "application/json"}
        if credential is not None and credential.scheme != "none" and credential.value:
            headers["Authorization"] = f"Bearer {credential.value}"
        body: dict[str, Any] = {
            "model": self._model,
            "prompt": _prompt(query, evidence),
            "stream": False,
        }
        if options is not None:
            ollama_options: dict[str, Any] = {}
            if options.temperature is not None:
                ollama_options["temperature"] = options.temperature
            if options.max_output_tokens is not None:
                ollama_options["num_predict"] = options.max_output_tokens
            if ollama_options:
                body["options"] = ollama_options
        response = self._http_post(f"{self._base_url}/api/generate", headers=headers, payload=body)
        return QueryAnswer(message=_message_from_payload(response), grounding="stored_ideas")


def _prompt(query: str, evidence: Sequence[AnswerEvidence]) -> str:
    evidence_lines = "\n".join(
        f"[{index}] {item.idea_id}: {item.snippet}" for index, item in enumerate(evidence, start=1)
    )
    return f"Answer only from stored idea evidence.\n\nQuery: {query}\nEvidence:\n{evidence_lines}"


def _message_from_payload(payload: dict[str, Any]) -> str:
    message = payload.get("response")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Ollama response did not include response text.")
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
        raise ValueError("Ollama response body must be a JSON object.")
    return payload
