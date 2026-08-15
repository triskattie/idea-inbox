# Spec: Idea Inbox MVP Architecture

## Status

Drafted for MVP implementation planning.

## Source context

This spec consolidates the repository discovery in
[`mvp-discovery-inventory.md`](mvp-discovery-inventory.md) and the existing project sources:

- [`initial-product-spec.md`](initial-product-spec.md)
- [`../architecture.md`](../architecture.md)
- [`../connectors.md`](../connectors.md)
- [`../providers.md`](../providers.md)
- [`../self-hosting.md`](../self-hosting.md)
- [`sqlite-schema-plan.md`](sqlite-schema-plan.md)
- [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)
- [`../decisions/ADR-001-connector-and-provider-boundaries.md`](../decisions/ADR-001-connector-and-provider-boundaries.md)
- [`../decisions/ADR-002-sqlite-default-postgres-production.md`](../decisions/ADR-002-sqlite-default-postgres-production.md)
- [`../decisions/ADR-003-cited-retrieval-answers.md`](../decisions/ADR-003-cited-retrieval-answers.md)
- [`../decisions/ADR-004-credential-providers.md`](../decisions/ADR-004-credential-providers.md)
- [`../decisions/ADR-005-raw-events-derived-ideas.md`](../decisions/ADR-005-raw-events-derived-ideas.md)
- [`../decisions/ADR-006-mvp-scope-and-local-first-self-hosting.md`](../decisions/ADR-006-mvp-scope-and-local-first-self-hosting.md)

## Product goal

Idea Inbox is a lightweight, self-hosted assistant for capturing ideas from inbox-like sources and querying them later with answers that cite stored ideas. The MVP optimizes for a single self-hosting operator and contributor-friendly extension points before broad platform coverage.

Success means a user can run the app locally, capture ideas through a manual API, preserve the original input as raw events, derive searchable ideas, search them through SQLite, and ask a query endpoint for retrieval-grounded answers with citations. Additional connectors and providers must fit behind stable interfaces rather than requiring core rewrites.

## Non-goals

The MVP does not include:

- A full web application UI.
- Multi-user accounts, organizations, role-based access control, or sharing permissions.
- Unofficial account-scraping connectors, including unofficial WhatsApp scraping.
- Complex autonomous workflows or agent orchestration.
- A requirement for paid hosted models or OpenAI API keys.
- Production-only infrastructure as the default path.

## User-facing MVP scope

### In scope

1. Local/self-hosted app process with a versioned `/v1` HTTP API.
2. Manual idea capture endpoint for direct text input.
3. Raw event ingestion and idempotent normalization into ideas.
4. SQLite default storage with migrations and FTS-backed keyword search.
5. Provider interfaces for answer generation and embeddings, with deterministic mocks for tests.
6. Query endpoint that returns cited answers or an explicit no-evidence response.
7. Connector interfaces and first connector modules for manual API, generic webhook, Telegram, email/IMAP, and Discord.
8. Optional Postgres + pgvector deployment profile after the SQLite path is healthy.
9. Self-hosting docs and configuration examples that match implemented commands.

### Out of scope until after MVP

- Browser/mobile UI beyond API-friendly responses.
- Multi-user ownership semantics beyond future-proof field naming where low-cost.
- Streaming answers, long-running background enrichment, and advanced ranking.
- OAuth/device login implementations; only the contract must allow them later.
- WhatsApp Cloud API support unless the official API path is separately specified.

## Development standards and Definition of Done

Development follows the repository workflow in `CONTRIBUTING.md`:

```text
SPEC → PLAN → TASKS → TEST → IMPLEMENT → VERIFY → REVIEW → COMMIT
```

Every behavior change must include:

- Written spec or accepted issue with explicit acceptance criteria.
- RED/GREEN/REFACTOR TDD for behavior changes.
- Deterministic tests for provider and connector behavior; no real Discord, Telegram, email, or model calls in normal tests.
- Thin route handlers; domain logic in services/core modules.
- Dependency injection over global clients.
- No provider SDK types imported by core domain code.
- No secrets in logs or committed files.
- Docs and ADR updates when public behavior or architecture changes.

A change is done only when:

- The relevant acceptance criteria are satisfied.
- Targeted tests and the project verification command pass.
- Query behavior tests verify citations.
- SQLite development mode remains healthy.
- API responses follow the `/v1` and error-shape standards.
- The handoff states what was touched and what was intentionally left out.

Runnable verification commands for the current repository are:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

If `uv` is unavailable, workers may use an isolated virtual environment for `pytest` and `ruff`, but should record the fallback in their handoff. Type checking with `mypy` is planned but must not be required in local verification or CI until `mypy` is added to the dev dependency group and configured in `pyproject.toml`.

## Architecture overview

The core data flow is:

```text
External source → Connector → RawEvent → IdeaDraft → Idea → Indexes → Query → Cited answer
```

Recommended module boundaries:

```text
src/idea_inbox/
  api/              HTTP app, /v1 routes, request/response schemas, error mapping
  core/             domain models, protocols, services, validation-independent business rules
  connectors/       manual, webhook, telegram, email, discord connector adapters
  providers/        model, embedding, and credential provider implementations
  storage/          storage backend protocol, SQLite implementation, migrations
  search/           search index protocol, SQLite FTS implementation, hybrid search later
  config.py         typed settings loaded from env/config files
  cli.py            command entry point, including dev/server commands
```

Core code may depend on protocols and plain domain data types only. Adapter modules depend inward on core contracts. API routes, connector handlers, provider implementations, and storage backends should be replaceable without changing the core ingestion/query services.

### Current implementation baseline

The repository now has first-pass configuration, SQLite storage, migrations, reusable manual
capture validation, a SQLite FTS search adapter, and an importable WSGI API app for manual
capture plus search endpoints. `POST /v1/ideas` validates and normalizes a JSON object with
non-empty `text` plus optional `source_ref`, `actor_ref`, `captured_at`, `metadata`, and `tags`;
it stores a manual raw event before persisting one draft and one canonical idea. `pyproject.toml`
exposes the `idea-inbox` console script at `idea_inbox.cli:main`; `src/idea_inbox/cli.py`
parses `dev`, `migrate`, and `serve`; `idea-inbox migrate` applies deterministic SQLite
migrations for the configured database or an explicit `--database` path; and `idea-inbox dev` /
`idea-inbox serve` start the WSGI API after applying pending migrations.

User-facing docs distinguish the smoke command (`uv run idea-inbox`), the runnable migration
command, the importable WSGI app surface, and the long-running CLI startup commands. Direct
content-management CLI commands such as `idea-inbox capture`, `idea-inbox search`, and
`idea-inbox query` remain intentionally deferred while the MVP uses `/v1` HTTP endpoints first.

## Core domain concepts and interfaces

The first implementation should define plain, SDK-free domain models in `idea_inbox.core.models` and narrow protocols in `idea_inbox.core.ports` or equivalent modules.

### Domain models

`RawEvent`

- Purpose: preserve original provider input before any normalization.
- Required fields:
  - `id`: internal stable identifier.
  - `source`: connector/source name such as `manual`, `webhook`, `telegram`, `email`, or `discord`.
  - `provider_event_id`: provider-supplied message/event identifier when available.
  - `dedupe_key`: source-scoped idempotency key.
  - `received_at`: timestamp when Idea Inbox accepted the event.
  - `occurred_at`: provider event timestamp when available.
  - `actor_ref`: source-specific sender reference, stored as metadata rather than an account model.
  - `payload`: raw JSON/text payload sufficient for debugging and reprocessing.
  - `payload_hash`: stable hash for duplicate detection and audit checks.
  - `processing_state`: `pending`, `processed`, `ignored`, or `failed`.
  - `error`: optional processing error code/message safe for logs.

`IdeaDraft`

- Purpose: normalized candidate extracted from a raw event before persistence as a canonical idea.
- Required fields:
  - `raw_event_id`.
  - `text`.
  - `source_created_at`.
  - `source_uri` or source reference when available.
  - `metadata` for connector-specific non-secret fields.

`Idea`

- Purpose: canonical searchable idea that query answers may cite.
- Required fields:
  - `id`.
  - `raw_event_id`.
  - `text`.
  - `created_at` and `updated_at`.
  - `captured_at`, based on provider time or ingest time.
  - `source` and `source_ref`.
  - `tags` as a simple list or derived metadata field.
  - `embedding_state`: `not_requested`, `pending`, `embedded`, or `failed`.

`SearchHit`

- Purpose: retrieval result passed into answer generation.
- Required fields:
  - `idea_id`.
  - `text`.
  - `score`.
  - `rank`.
  - `source`.
  - `captured_at`.
  - `snippet`.

`Citation`

- Purpose: answer evidence that points back to stored ideas.
- Required fields:
  - `idea_id`.
  - `quote` or `snippet`.
  - `source`.
  - `captured_at`.

### Core service interfaces

`Connector`

- Validates external payloads at the boundary.
- Builds one `RawEventInput` per incoming external event.
- Extracts zero or more `IdeaDraft` records from a persisted raw event.
- Does not expose provider SDK objects outside the connector module.

Expected protocol shape:

```text
Connector.name -> str
Connector.validate(payload, headers, credentials) -> ValidatedConnectorEvent
Connector.to_raw_event(validated_event) -> RawEventInput
Connector.extract_drafts(raw_event) -> list[IdeaDraft]
```

`StorageBackend`

- Owns persistence, transactions, migrations, and idempotent writes.
- Provides raw event, idea, and query-supporting reads without leaking database driver types.

Expected protocol shape:

```text
StorageBackend.save_raw_event(input) -> RawEvent
StorageBackend.mark_raw_event_processed(raw_event_id, result) -> None
StorageBackend.save_idea(draft) -> Idea
StorageBackend.get_idea(idea_id) -> Idea | None
StorageBackend.list_ideas(page) -> Page[Idea]
StorageBackend.transaction() -> context manager
```

`SearchIndex`

- Indexes ideas and returns ranked hits.
- Starts with SQLite FTS; hybrid/vector ranking is added behind the same contract.

Expected protocol shape:

```text
SearchIndex.upsert_idea(idea) -> None
SearchIndex.search(query, limit, filters) -> list[SearchHit]
SearchIndex.delete_idea(idea_id) -> None
```

`ModelProvider`

- Generates retrieval-grounded answers from a query and retrieved evidence.
- Must support a deterministic mock implementation for tests.
- Must not fetch credentials directly from environment variables.

Expected protocol shape:

```text
ModelProvider.answer(query, evidence, options) -> AnswerDraft
```

`EmbeddingProvider`

- Generates embeddings for ideas and queries when hybrid search lands.
- Initial MVP may define the protocol before enabling vector ranking.

Expected protocol shape:

```text
EmbeddingProvider.embed_texts(texts, options) -> list[Embedding]
```

`CredentialProvider`

- Supplies credentials to providers/connectors without hardcoding the credential source.
- MVP providers can be `none`, `env_api_key`, and `static_config`.
- The contract must leave room for OAuth/device-code, Codex-style, Hermes/proxy, browser-login, and local flows.

Expected protocol shape:

```text
CredentialProvider.get(scope, account_ref=None) -> Credential | None
```

`IngestionService`

- Coordinates connector validation, raw event persistence, draft extraction, idea persistence, and indexing.
- Must persist `RawEvent` before deriving or indexing ideas.
- Must be idempotent by source and dedupe key.

Expected operation:

```text
ingest(source, payload, headers) -> IngestResult(raw_event, ideas, duplicate)
```

`QueryService`

- Searches stored ideas, calls the model provider only with retrieved evidence, and returns citations.
- If no relevant evidence exists, returns a no-evidence response without hallucinated content.

Expected operation:

```text
answer(query, limit, filters) -> QueryAnswer(answer, citations, hits)
```

## API design

All public endpoints use `/v1` and the standard error shape from `CONTRIBUTING.md`. The current
runtime dependency-free WSGI implementation performs manual boundary validation with dataclass
request DTOs instead of Pydantic schemas; keep that stdlib path until an external schema/framework
dependency is explicitly accepted. List/search endpoints use paginated response envelopes.

### Manual capture

```text
POST /v1/ideas
```

Request:

```json
{
  "text": "Idea text",
  "source_ref": "optional caller reference",
  "actor_ref": "optional local operator/source reference",
  "captured_at": "optional ISO-8601 timestamp",
  "metadata": {},
  "tags": ["optional", "labels"]
}
```

Response `201 Created`:

```json
{
  "item": {
    "idea_id": "idea_...",
    "text": "Idea text",
    "source": "manual",
    "source_ref": "optional caller reference",
    "captured_at": "2026-08-09T00:00:00Z",
    "metadata": {},
    "tags": ["optional", "labels"]
  }
}
```

The manual capture API boundary intentionally returns the newly captured `item` only. Raw event lineage and duplicate/idempotency bookkeeping remain persisted internally by the ingestion/storage layer and can be exposed by later dedicated read or audit endpoints if the MVP needs them. This keeps the public manual-create response aligned with the accepted strict-xfail contract in `tests/test_api_manual_ideas.py` while preserving the raw event → idea persistence requirement.

Implemented validation behavior:

- The request body must be a JSON object.
- `text` is required, trimmed, and must be a non-empty string no longer than 10,000 characters.
- `source_ref`, `actor_ref`, and `captured_at` are optional strings; blank values normalize to
  `null`, and `source_ref`/`actor_ref` are limited to 512 characters. `captured_at` is currently
  stored as a caller-provided string when present; strict timestamp parsing is deferred.
- `metadata` is optional and must be a JSON object.
- `tags` is optional and must be a JSON list of strings. Tags are trimmed, lower-cased,
  de-duplicated in first-seen order, ignore blank entries, allow at most 50 submitted items, and
  each normalized tag is limited to 64 characters.
- Validation failures return `400 VALIDATION_ERROR` with the failing field in
  `error.details.field`; storage failures return `500 STORAGE_ERROR` without exposing internals.

Known MVP limitations: manual capture does not yet accept or enforce an idempotency-key header,
so replayed requests create new raw events and ideas; the endpoint also has no application-level
access-token gate yet and should be bound to localhost or protected by external network controls
when self-hosted.

### Generic connector ingestion

```text
POST /v1/connectors/{connector_name}/events
```

This endpoint is used for generic webhooks and future connector handlers. Connector modules own source-specific validation and conversion into raw events. Unsupported connector names return `404` or a typed `CONNECTOR_NOT_FOUND` error.

### Search ideas

```text
GET /v1/ideas/search?q=...&limit=10
```

Response:

```json
{
  "items": [
    {
      "idea_id": "idea_...",
      "snippet": "...",
      "score": 12.3,
      "source": "manual",
      "captured_at": "2026-08-09T00:00:00Z"
    }
  ],
  "page": { "limit": 10, "next_cursor": null }
}
```

Implemented behavior as of the FTS search slice:

- The endpoint is available from `idea_inbox.api.create_app` and reads the configured SQLite
  database path unless an explicit `database_path` is injected for tests.
- `q` is required after normalization. The search adapter extracts Unicode word tokens,
  ignores punctuation, quotes every token, and passes the normalized string to SQLite FTS.
- Searchable fields are `Idea.text`, normalized tags, and `Idea.source_ref`. Raw event
  payloads are preserved in storage but are not indexed by `idea_fts` and are not returned by
  this response.
- Raw SQLite FTS query syntax is intentionally not exposed yet; boolean operators, prefix
  wildcards, `NEAR`, column filters, and caller-supplied quotes are treated as words or
  punctuation by the normalizer.
- `limit` defaults to `10` and must be from `1` through `50`; invalid limits and empty queries
  use the standard `400 VALIDATION_ERROR` response shape.
- Results are ordered by `bm25(idea_fts)`, then newest capture timestamp, then stable idea id.
  `next_cursor` is currently always `null`.

### Query with cited answer

```text
POST /v1/query
```

Request:

```json
{
  "query": "What ideas did I save about local AI?",
  "limit": 10
}
```

Response with evidence:

```json
{
  "answer": "You saved two ideas about local AI...",
  "citations": [
    {
      "idea_id": "idea_...",
      "quote": "local AI should work without hosted APIs",
      "source": "manual",
      "captured_at": "2026-08-09T00:00:00Z"
    }
  ],
  "hits": []
}
```

Response without evidence:

```json
{
  "answer": "I could not find stored ideas relevant to that query.",
  "citations": [],
  "hits": []
}
```

The query endpoint must never present generated claims as grounded unless at least one stored idea citation is returned.

## Storage design

SQLite is the default MVP storage backend. The first SQLite implementation should live behind the `StorageBackend` contract so Postgres support can be added without changing services or routes.

Required SQLite tables:

`raw_events`

- `id` primary key.
- `source` text not null.
- `provider_event_id` text nullable.
- `dedupe_key` text not null.
- `received_at` timestamp not null.
- `occurred_at` timestamp nullable.
- `actor_ref` text nullable.
- `payload` text/blob not null.
- `payload_hash` text not null.
- `processing_state` text not null.
- `error_code` text nullable.
- `error_message` text nullable.
- Unique index on `(source, dedupe_key)`.

`ideas`

- `id` primary key.
- `raw_event_id` foreign key to `raw_events.id`.
- `text` text not null.
- `source` text not null.
- `source_ref` text nullable.
- `captured_at` timestamp not null.
- `created_at` timestamp not null.
- `updated_at` timestamp not null.
- `metadata` text/json not null default `{}`.
- `embedding_state` text not null.

`idea_fts`

- SQLite FTS5 virtual table over canonical idea `text`, normalized `tags`, and `source_ref`,
  with `content='ideas'` and `content_rowid='rowid'` so results join back to stable
  `ideas.id` values.
- Kept in sync by SQLite triggers when ideas are inserted, updated, or deleted. The migration
  ends with an FTS rebuild for existing rows, and the search adapter exposes a rebuild method
  for projection repair.

`embeddings`

- May be created when embedding support lands.
- Stores idea id, provider id, vector dimensions, vector payload, and timestamps.
- SQLite vector storage can be simple serialized blobs until a better local extension is specified.

Migrations should be deterministic files in the repository, applied by CLI/server startup in dev mode or through an explicit migration command. Tests should run against temporary SQLite databases. The concrete first-pass table list, data mapping, indexes, timestamps, and migration order are maintained in [`sqlite-schema-plan.md`](sqlite-schema-plan.md).

## Search design

MVP search ships in two layers:

1. Keyword/FTS search is required for the first query-capable slice.
2. Embeddings/hybrid search is added only after FTS search and cited query behavior are tested.

FTS requirements:

- Index canonical `Idea` records, not raw events directly.
- Return stable `SearchHit` values with idea id, snippet, score, source, and capture timestamp.
- Support `limit` from day one.
- Keep ranking deterministic in tests.

Hybrid search requirements:

- Use `EmbeddingProvider` for idea and query embeddings.
- Preserve the `SearchIndex.search(...)` contract so callers do not know whether FTS, vector, or hybrid ranking produced the hit.
- Do not require external hosted embedding services; local embedding providers must be possible.

## Provider design

Provider implementations are adapters. Core query services depend on `ModelProvider`, `EmbeddingProvider`, and `CredentialProvider` protocols only.

Required MVP providers:

- `mock_model`: deterministic answer provider for tests and offline development.
- `mock_embedding`: deterministic embedding provider for tests.
- `openai_compatible_model`: HTTP provider compatible with OpenAI-style APIs.
- `ollama_model`: local provider if the local endpoint is configured.
- `local_embedding`: local embedding provider when embedding support lands.
- `none`, `env_api_key`, and `static_config` credential providers.

Provider rules:

- No provider may read secrets directly unless it is a credential provider.
- Provider config must identify the provider type, model name, base URL if applicable, and credential provider reference.
- Constructors must not perform hidden network calls.
- Retries/timeouts should be explicit configuration and testable.
- Normal tests use mocks; optional integration tests may require explicit environment flags.

## Connector design

Connectors are source-specific adapters that turn untrusted external payloads into raw events and drafts. Core ingestion services should not know Telegram, Discord, email, or webhook SDK types.

Required connector sequence:

1. `manual`: backs `POST /v1/ideas` and exercises the full raw event → idea → index path.
2. `webhook`: validates generic webhook payloads and signatures if configured.
3. `telegram`: validates Telegram update payloads and preserves update/message ids.
4. `email_imap`: polls or receives email messages, preserving message IDs and mailbox metadata.
5. `discord`: validates Discord events/interactions and preserves channel/message ids.

Connector requirements:

- Validate payload shape at the boundary.
- Preserve provider IDs for idempotency.
- Construct raw event payloads without dropping source evidence needed for debugging.
- Extract zero or more idea drafts from a single raw event.
- Use connector-specific credential providers for tokens/passwords.
- Keep retries and polling cadence configurable.
- Never log secrets or full sensitive payloads at info level.

## Privacy and security assumptions

MVP security is single-operator self-hosting, not multi-tenant SaaS.

Assumptions:

- The operator controls the deployment and storage location.
- Local SQLite files and Postgres data directories are sensitive user data.
- Connector payloads may contain private chat/email content.
- Model providers may receive retrieved idea text unless a local/mock provider is configured.
- Hosted model use is optional and must be visible in configuration.

Requirements:

- No secrets in repository files, logs, test fixtures, or errors.
- Manual/API access requires an operator-configured credential before network exposure.
- Webhook/connector endpoints validate signatures or tokens where the source supports them.
- Stored raw payloads are preserved for audit/reprocessing but should not be returned by default list/query endpoints.
- Error responses expose safe codes/messages, not raw stack traces or secrets.
- The docs must make clear when data leaves the host for an external model provider.

Deferred security work:

- Multi-user authorization.
- Fine-grained retention/redaction controls.
- End-to-end encryption.
- Admin UI for credential management.

## Configuration and CLI

The CLI entry point is `idea_inbox.cli:main`. MVP commands should converge on:

```bash
idea-inbox dev
idea-inbox migrate
idea-inbox serve --host 127.0.0.1 --port 8080
```

`dev` should run the local API with SQLite and mock/local providers by default. It should fail with actionable messages when required configuration is missing.

These are target MVP commands. Phase 1 implements command parsing before the API, storage, and server runtimes exist. Documentation that describes current setup should continue to use the existing smoke command and explicitly label `dev`, `migrate`, and `serve` as startup targets until their underlying runtime modules are implemented.

### Planned CLI command contract

The CLI is an operator/developer control surface for running the local service and managing
storage. Idea capture, search, and cited query behavior are exposed first through the `/v1`
HTTP API, not through direct content-management CLI commands.

Common behavior:

- `idea-inbox --help` prints the available commands and exits `0`.
- `idea-inbox <command> --help` prints command-specific options and exits `0`.
- Unknown commands or invalid options print a short usage error and exit `2`.
- Missing configuration, unavailable ports, failed migrations, or startup failures print an
  actionable error without secrets and exit `1`.
- Successful one-shot commands exit `0`; long-running server commands exit `0` on graceful
  shutdown and `1` on startup/runtime failure.

`idea-inbox dev`

- Purpose: start the local development API using SQLite and mock/local providers by default.
- Options: `--host` and `--port` may override the default bind address and port; database URL
  and log level are read from the same configuration surface used by the server.
- Behavior: loads development configuration, ensures the SQLite database is ready, starts the
  `/v1` API, and clearly reports the local URL. It must not require hosted-model credentials,
  hidden outbound model calls, or telemetry.
- Conservative assumption: dev startup may apply pending SQLite migrations automatically because
  SQLite dev mode must stay healthy; if that proves unsafe, implementation should require an
  explicit `idea-inbox migrate` run and document the reason.

`idea-inbox migrate`

- Purpose: apply deterministic repository migrations for the configured storage backend.
- Options: database URL/path may be provided through configuration; a future `--check` option may
  report pending migrations without applying them if migration metadata needs it.
- Behavior: applies pending migrations idempotently, prints the resulting migration state, and
  exits `0` when the database is current. Migration failures exit `1` without partially hiding the
  failed migration name/version.

`idea-inbox serve --host 127.0.0.1 --port 8080`

- Purpose: start the configured API process for local or self-hosted use.
- Options: `--host` and `--port` set the bind address. Provider, credential, database, connector,
  and log-level settings come from configuration rather than ad hoc command-line secrets.
- Behavior: validates required configuration before accepting requests, starts the `/v1` API, and
  refuses unsafe network exposure when required operator credentials are missing. Hosted model
  providers remain optional and must be visible in configuration.

Intentionally deferred CLI commands:

- Direct `idea-inbox capture`, `idea-inbox search`, or `idea-inbox query` commands are deferred;
  the first MVP contract uses `POST /v1/ideas`, `GET /v1/ideas/search`, and `POST /v1/query`.
- Connector worker commands such as `telegram poll`, `email poll`, or `discord listen` are deferred
  until connector runtime modes, credentials, retries, and fixture-driven tests are specified.
- Admin/export/import, provider login, OAuth/device authorization, backup/restore, retention, and
  redaction commands are deferred until their storage, privacy, and credential contracts exist.

Configuration should cover:

- SQLite database URL/path.
- Log level.
- API/manual access token.
- Model provider type, base URL, model name, and credential provider reference.
- Embedding provider type, model name, and credential provider reference.
- Telegram, Discord, email, and webhook credentials/settings when those connectors are enabled.

## MVP implementation phases

### Phase 1: Executable skeleton and project health

Acceptance criteria:

- `idea-inbox --help` and `idea-inbox dev` exist.
- SQLite database path and log level are configurable.
- `pytest` and `ruff` pass in the documented environment.
- Docs do not advertise commands that fail by design without a tracked issue/spec note.

### Phase 2: Domain models and storage contract

Acceptance criteria:

- `RawEvent`, `IdeaDraft`, `Idea`, `SearchHit`, and `Citation` models exist.
- `StorageBackend` protocol and SQLite implementation exist.
- Raw events are saved idempotently by `(source, dedupe_key)`.
- Temporary SQLite tests cover migrations, raw event insert, duplicate insert, and idea insert.

### Phase 3: Manual ingestion API

Acceptance criteria:

- `POST /v1/ideas` persists a raw event before deriving ideas.
- Manual capture creates at least one canonical idea and indexes it.
- Duplicate requests do not create duplicate raw events or ideas.
- Route tests assert the standard error shape for invalid input.

### Phase 4: Keyword search

Acceptance criteria:

- SQLite FTS index is created and maintained.
- `GET /v1/ideas/search` returns paginated, ranked hits with snippets.
- Tests cover no-results, ranking stability, and limit behavior.

### Phase 5: Cited query endpoint

Acceptance criteria:

- `POST /v1/query` retrieves ideas before answer generation.
- The model provider receives only the query and retrieved evidence.
- Responses include citations pointing to stored idea IDs.
- No-evidence queries return an explicit no-evidence response.
- Tests use deterministic mock providers and verify citation behavior.

### Phase 6: Provider adapters

Acceptance criteria:

- Model, embedding, and credential provider protocols are stable enough for contributors.
- Mock providers are used by default in tests.
- OpenAI-compatible and local/Ollama providers are isolated from core services.
- Secrets flow through credential providers, not direct environment reads in model providers.

### Phase 7: Connector modules

Acceptance criteria:

- Manual and generic webhook connectors exercise the same ingestion service.
- Telegram, email/IMAP, and Discord connectors can parse fixture payloads into raw events and drafts.
- Normal tests never call real platforms.
- Provider IDs are preserved for idempotency.

### Phase 8: Optional Postgres + pgvector profile

Acceptance criteria:

- Postgres storage/search implementation satisfies the same service contracts as SQLite.
- Docker Compose config documents Postgres + pgvector setup.
- SQLite remains the default dev path.
- Tests clearly separate always-run unit/SQLite tests from opt-in Postgres integration tests.

## MVP acceptance criteria

The MVP is accepted when all of the following are true:

1. A fresh contributor can install dependencies, run tests, and start the local app from documented commands.
2. Manual idea capture creates a raw event, derives an idea, stores both, indexes the idea, and returns stable identifiers.
3. Duplicate manual or connector events are idempotent by source and dedupe key.
4. Keyword search returns stored ideas with deterministic ranking and snippets.
5. Query answers cite stored ideas and refuse to invent evidence when no relevant ideas are found.
6. Connector/provider/storage/search/core boundaries are enforced by imports, tests, and interfaces.
7. Normal tests use mocks/fixtures and make no real platform or model calls.
8. SQLite is healthy as the default local backend.
9. Optional hosted AI paths are configurable but not required.
10. Docs link the implemented command/configuration surface and note which connectors/providers are available versus planned.

## Implementation review notes and risks

This spec has been checked against the current repository skeleton, `CONTRIBUTING.md`, `pyproject.toml`, the README, supporting docs, and ADR-001 through ADR-006. The main boundaries are implementable in small TDD slices, with these constraints for downstream tasks:

1. Phase 1 is a prerequisite for later implementation. The target module layout, `idea-inbox dev`, `idea-inbox migrate`, and `idea-inbox serve` do not exist yet, so later tasks should not assume route, storage, connector, or provider packages are present before creating them with tests.
2. Verification must match configured tooling. `pytest`, `ruff check`, and `ruff format --check` are current gates; `mypy` remains planned until configured.
3. API pagination needs a concrete shared schema before the first list/search route lands. Use a cursor or limit/offset shape consistently, test invalid limits, and keep all list endpoints paginated from day one.
4. Persistence and indexing need an explicit consistency rule. `IngestionService` should save raw events and ideas transactionally, then update `SearchIndex` in a way that can be retried or rebuilt without losing the authoritative storage record.
5. ID and timestamp generation should be centralized before multiple adapters exist, so connectors do not invent incompatible identifiers or timezone handling.
6. `CredentialProvider.get(...)` needs a concrete return type before real providers land. It should support no-secret/local/mock flows and avoid forcing model providers to know whether credentials came from env vars, static config, OAuth, a proxy, or local auth.
7. Connector implementation order should start with manual API and generic webhook fixtures before platform SDKs. Telegram, email, and Discord connector work should stay fixture-driven until credentials, polling/webhook modes, and retry behavior are specified.
8. Citation behavior should resolve final citations through stored `Idea` records and raw-event lineage, not only through FTS snippets or model-generated references.
9. Multi-user ownership remains out of scope. If future-proof fields are introduced, they should be nullable metadata or clearly single-operator placeholders, not implicit security boundaries.

## Future work

These items are intentionally outside the MVP spec but should remain possible through the chosen interfaces:

- Multi-user accounts, ownership, RBAC, and sharing.
- Rich web UI and browser extensions.
- Advanced summarization, clustering, tagging, and background enrichment.
- OAuth/device-code/Codex-style credential providers.
- Additional official connectors such as WhatsApp Cloud API.
- Retention policies, redaction workflows, and encrypted storage.
- Streaming answers and conversational query sessions.
