# Provider Guide

Providers supply optional model, embedding, and credential capabilities without leaking provider-specific SDKs or auth flows into the core domain. The base app must run without provider modules enabled.

## Model providers

Current implementation status: model and embedding provider config keys are mostly reserved. The
capability registry reads `IDEA_INBOX_CHAT_PROVIDER` only when `query-ai` is explicitly enabled by
an in-process registry override; the normal `dev`/`serve` path does not expose a public toggle and
keeps query disabled. `.env.example` includes `IDEA_INBOX_CHAT_PROVIDER`,
`IDEA_INBOX_EMBEDDING_PROVIDER`, `IDEA_INBOX_OPENAI_BASE_URL`, `IDEA_INBOX_OPENAI_API_KEY`,
`IDEA_INBOX_OPENAI_CHAT_MODEL`, and `IDEA_INBOX_OPENAI_EMBEDDING_MODEL` to show the planned
provider shape; setting them does not enable provider-backed answer generation in the current
runtime.

The core must not assume OpenAI API keys. Supported paths should include:

- mock provider for tests
- OpenAI-compatible HTTP provider
- Ollama/local provider
- local sentence-transformer embedding provider
- OAuth/proxy/Codex-style credential flows later

Model and embedding providers own generation/embedding API calls and provider-specific request mapping only. They are installed/enabled deliberately by the operator and must not be invoked by base startup, migration, capture, or FTS search. They request secrets or session material through `CredentialProvider`; they do not store secrets, refresh OAuth tokens, run browser login flows, or decide how credentials are persisted.


## Deterministic mock query foundation

The v0.2.0 query path uses deterministic/mock behavior for tests and local harnesses, not a real
provider ecosystem. A harness may install a `model-provider` capability record, set
`enabled_overrides={"query-ai": True}`, and provide `IDEA_INBOX_CHAT_PROVIDER=mock` through
`CapabilityRegistry(config_values=...)`. That enables `POST /v1/query` to retrieve stored ideas
through SQLite FTS and build a deterministic cited answer.

This mock path is deliberately not general model-provider support: it does not import provider SDKs,
call OpenAI-compatible endpoints, talk to Ollama, compute embeddings, rerank, stream, or use model
world knowledge. The default packaged server remains disabled until a later provider-adapter slice
adds an operator-facing enablement surface.

## Credential providers

Credential providers allow a model provider to request credentials without knowing where they came from. They own credential lookup, refresh, and persistence policy for API-key, local, OAuth/device-code, proxy, and Codex-style login paths.

Initial providers can be simple:

- `none`
- `env_api_key`
- `static_config`

Future providers:

- `oauth_device_code`
- `codex_login`
- `hermes_proxy`
- `browser_login`

Core contracts should accept credential handles or resolved request auth data, not provider SDK credential objects, so future auth paths remain swappable.
