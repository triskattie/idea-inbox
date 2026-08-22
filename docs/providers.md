# Provider Guide

Providers supply optional model, embedding, and credential capabilities without leaking provider-specific SDKs or auth flows into the core domain. The base app runs without provider modules enabled.

## Implementation status

Phase 7 adds an SDK-free provider-adapter surface and offline-tested adapter boundaries:

- Core contracts in `idea_inbox.core.ports`: `ModelProvider`, `EmbeddingProvider`, `CredentialProvider`, `CredentialRequest`, `CredentialMaterial`, and `ModelProviderOptions`.
- Capability metadata from `idea_inbox.providers.capabilities.provider_capabilities()` for `model-provider`, `mock-model-provider`, `openai-compatible-model-provider`, `ollama-model-provider`, `embedding-provider`, `none-credentials`, `env-api-key-credentials`, and `static-config-credentials`.
- Deterministic offline mock providers in `idea_inbox.providers.mock`.
- OpenAI-compatible and Ollama request-mapping adapters in `idea_inbox.providers.openai_compatible` and `idea_inbox.providers.ollama`.

The normal `dev`/`serve` path still constructs `create_app()` with the default `CapabilityRegistry()`, so `query-ai` remains disabled by default. Setting `IDEA_INBOX_CHAT_PROVIDER=mock` in `.env` alone does not enable query. A test or embedded harness must deliberately install provider capability metadata, enable `query-ai`, enable `model-provider`, enable the selected concrete provider, and inject a provider implementation when it wants provider-backed answers.

This is now an implemented adapter boundary, but it is still not general model-provider support in the packaged server path: there is no public CLI toggle, package discovery, streaming, tool calling, embeddings/vector ranking, OAuth/device login, or automatic provider startup.

## Model providers

Model providers implement the `ModelProvider` protocol. They receive only the user query, provider-neutral options, and retrieved `AnswerEvidence` records that were resolved from stored `Idea` rows. They must not retrieve ideas themselves, inspect raw event payload bodies by default, or return provider SDK response objects to core query code.

Implemented provider boundaries:

- `mock-model-provider`: deterministic offline provider for tests and local harnesses.
- `openai-compatible-model-provider`: maps stored evidence to a `/chat/completions`-style request using a credential provider for auth.
- `ollama-model-provider`: maps stored evidence to a local `/api/generate` request and supports a no-secret local credential mode.

Provider calls are skipped for no-evidence responses in the current query contract; the service returns the explicit `no_relevant_stored_ideas` answer with empty citations instead.

## Capability enablement

Provider capabilities are opt-in metadata records. Example in-process test/harness setup for the deterministic provider:

```python
from idea_inbox.api import create_app
from idea_inbox.capabilities.registry import CapabilityRegistry
from idea_inbox.providers.capabilities import provider_capabilities
from idea_inbox.providers.mock import MockModelProvider

registry = CapabilityRegistry(
    installed_capabilities=provider_capabilities(),
    enabled_overrides={
        "query-ai": True,
        "model-provider": True,
        "mock-model-provider": True,
        "none-credentials": True,
    },
    config_values={"IDEA_INBOX_CHAT_PROVIDER": "mock"},
)
app = create_app(
    database_path="./data/idea-inbox.sqlite3",
    capability_registry=registry,
    model_provider=MockModelProvider(),
)
```

`query-ai` validates the selected chat provider from `IDEA_INBOX_CHAT_PROVIDER` against the matching provider capability:

| `IDEA_INBOX_CHAT_PROVIDER` | Required provider capability |
| --- | --- |
| `mock` | `mock-model-provider` |
| `openai-compatible` | `openai-compatible-model-provider` |
| `ollama` | `ollama-model-provider` |

If the selected provider capability is missing, disabled, or misconfigured, `query-ai` reports a non-secret registry diagnostic and `POST /v1/query` returns `CAPABILITY_DISABLED` instead of performing retrieval or provider calls.

## Credential providers

Credential providers allow model providers to request credentials without knowing where they came from. They own credential lookup, refresh, and persistence policy for API-key, local, OAuth/device-code, proxy, and Codex-style login paths.

Implemented initial credential modes:

- `none` for local/no-secret providers such as Ollama or deterministic tests.
- `env_api_key` for resolving an API key by configured environment-key handle.
- `static_config` for explicitly supplied in-process static credentials in tests/harnesses.

Future providers remain additive: `oauth_device_code`, `codex_login`, `hermes_proxy`, and `browser_login`.

Registry diagnostics may name missing secret keys such as `IDEA_INBOX_OPENAI_API_KEY`, but must never expose secret values.

## Embedding providers

`EmbeddingProvider` is a stable placeholder contract for future embeddings and hybrid search. The Phase 7 slice includes deterministic mock embedding behavior and an `embedding-provider` capability shape, but it does not enable vector search, pgvector, hybrid ranking, or default embedding calls.

## Configuration keys

`.env.example` includes inert provider keys so operators can see the planned surface:

- `IDEA_INBOX_CHAT_PROVIDER`
- `IDEA_INBOX_EMBEDDING_PROVIDER`
- `IDEA_INBOX_OPENAI_BASE_URL`
- `IDEA_INBOX_OPENAI_API_KEY`
- `IDEA_INBOX_OPENAI_CHAT_MODEL`
- `IDEA_INBOX_OPENAI_EMBEDDING_MODEL`
- `IDEA_INBOX_OLLAMA_BASE_URL`
- `IDEA_INBOX_OLLAMA_CHAT_MODEL`

These values do not change base startup, migration, manual capture, or FTS search. They are read by capability validation only when the owning capability is explicitly enabled.
