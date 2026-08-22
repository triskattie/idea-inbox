# Phase 7 implementation brief: optional provider adapters

## Status

Implemented as the Phase 7 opt-in provider-adapter boundary. The implementation landed provider
protocols, provider capability metadata, deterministic mock providers, and OpenAI-compatible/Ollama
request-mapping adapters for explicit in-process harnesses. It intentionally did not add public
CLI/`.env` enablement, package discovery, automatic provider construction, streaming, embeddings or
vector search, connector ingestion, production auth, or default provider calls.

## Evidence inspected before implementation

- `docs/specs/mvp-architecture-spec.md`: Phase 7 acceptance criteria require stable model,
  embedding, and credential provider protocols; default mock providers in tests;
  OpenAI-compatible and local/Ollama adapters isolated from core services; secrets flowing through
  credential providers; and provider adapters remaining opt-in capabilities.
- `docs/providers.md`: provider configuration keys were reserved, the query path could only use a
  deterministic mock harness, and real hosted/local provider adapters remained later work.
- `docs/specs/cited-query-api-contract.md`: `POST /v1/query` is default-disabled and must answer
  only from persisted stored-idea evidence when enabled.
- `docs/architecture.md`, ADR-001, ADR-004, and ADR-007: core code must stay SDK-free, credential
  lifecycle belongs behind `CredentialProvider`, and AI/heavy integrations must not become base
  startup requirements.

## Implemented user-facing behavior

1. Fresh installs still start, migrate, capture manual ideas, and run SQLite FTS search without
   model credentials, embeddings, provider SDKs, hidden network calls, local model daemons, or
   connector tokens.
2. `POST /v1/query` remains disabled by default and returns the typed `CAPABILITY_DISABLED`
   response unless an in-process harness explicitly installs and enables `query-ai`,
   `model-provider`, a selected concrete provider capability, and its credential-provider
   capability.
3. Deterministic mock providers remain the default test and harness path.
4. OpenAI-compatible and local/Ollama provider paths are separate adapters behind SDK-free
   contracts. They receive only citation-safe stored-idea evidence and do not leak SDK types, raw
   secrets, or provider-specific response shapes into core query code.
5. Credential lookup is represented by `CredentialProvider` implementations such as `none`,
   `env_api_key`, and `static_config`, leaving room for later OAuth/device, Codex-style,
   Hermes/proxy, browser-login, and local no-secret flows.

## Implemented deliverables

- Provider protocol contract stabilization:
  - `src/idea_inbox/core/ports.py` defines `ModelProvider`, `EmbeddingProvider`,
    `CredentialProvider`, `CredentialRequest`, `CredentialMaterial`, and
    `ModelProviderOptions` without provider SDK imports.
- Mock provider foundation:
  - `src/idea_inbox/providers/mock.py` implements deterministic mock model, embedding, and
    credential providers for offline tests and local harnesses.
- Opt-in capability metadata and validation:
  - `src/idea_inbox/providers/capabilities.py` declares `model-provider`, `mock-model-provider`,
    `openai-compatible-model-provider`, `ollama-model-provider`, `embedding-provider`,
    `none-credentials`, `env-api-key-credentials`, and `static-config-credentials`.
  - Built-in `query-ai` remains `default_enabled=False` and validates the selected
    `IDEA_INBOX_CHAT_PROVIDER` against enabled provider metadata when a harness opts in.
- OpenAI-compatible adapter boundary:
  - `src/idea_inbox/providers/openai_compatible.py` maps stored evidence and provider-neutral
    options to a `/chat/completions` request using a credential provider. Tests fake the HTTP
    boundary and make no hosted calls.
- Local/Ollama adapter boundary:
  - `src/idea_inbox/providers/ollama.py` maps stored evidence and provider-neutral options to a
    local `/api/generate` request and supports a no-secret credential mode. Tests fake the HTTP
    boundary and do not require an Ollama daemon.
- Embedding-provider placeholder:
  - `EmbeddingProvider`, `MockEmbeddingProvider`, and `embedding-provider` capability metadata are
    present, but vector storage, hybrid ranking, pgvector, and default embedding calls remain out of
    scope.

## Boundary rules preserved

- Core domain/query code depends only on plain dataclasses/protocols; no provider SDK imports, HTTP
  response objects, OAuth sessions, or raw credential objects cross into core.
- Provider adapters receive only the validated query/options and citation-safe retrieved evidence.
  They must not retrieve ideas themselves, inspect raw event payload bodies by default, or use model
  world knowledge as uncited evidence.
- Credential providers own secret lookup, refresh, persistence policy, and login/session lifecycle.
  Model and embedding providers consume credential outputs rather than reading secrets directly from
  core query code.
- Capability registry validation remains side-effect-light. Listing or validating capabilities does
  not initialize adapters or make network calls.
- Provider config keys in `.env.example` stay inert until the owning capability is explicitly
  enabled in an in-process registry or future public enablement surface.

## Follow-up scope

The following remain future work and need their own specs before implementation:

- Public CLI/config enablement for provider-backed query.
- Package discovery or installable provider modules.
- Automatic provider construction from `.env` values in `dev`/`serve`.
- Streaming, tool calling, richer model options, or provider-specific response metadata.
- Real embedding adapters, vector storage, hybrid ranking, or pgvector deployment profiles.
- OAuth/device, Codex-style, Hermes/proxy, and browser-login credential providers.
