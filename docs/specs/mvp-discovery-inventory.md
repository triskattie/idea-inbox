# MVP discovery inventory

## Purpose

This note inventories the current Idea Inbox repository documentation and accepted decisions so a downstream worker can draft the full MVP spec without rereading the whole repo. It records repo evidence only; unresolved questions are intentionally kept separate from confirmed decisions.

## Resolution status

This is a source inventory snapshot, not the controlling MVP contract. The open questions below were resolved by `mvp-architecture-spec.md`; keep this file only as background evidence for how the MVP architecture spec was derived.

## Sources reviewed

- `README.md` — product summary, goals, planned MVP, quick start.
- `CONTRIBUTING.md` — development workflow, architecture rules, testing/API/git standards, definition of done.
- `AGENTS.md` — non-negotiable agent/project standards.
- `pyproject.toml` — current Python package metadata, command entry point, and tooling config.
- `.env.example` — current environment/configuration surface.
- `docs/specs/initial-product-spec.md` — objective, success criteria, MVP phases, and out-of-scope list.
- `docs/architecture.md` — core flow, stable concepts, design priorities.
- `docs/connectors.md` — connector contract and planned connector list.
- `docs/providers.md` — model, embedding, and credential provider assumptions.
- `docs/self-hosting.md` — lightweight and production deployment targets.
- `docs/decisions/ADR-001-connector-and-provider-boundaries.md` through `ADR-006-mvp-scope-and-local-first-self-hosting.md` — accepted architectural decisions.
- `CHANGELOG.md` — current repository status note.
- `src/idea_inbox/cli.py`, `src/idea_inbox/__init__.py`, and `tests/test_package_baseline.py` — implementation status check.

## Current product goal

Idea Inbox is a lightweight, self-hosted assistant for capturing ideas from multiple inbox-like sources and later querying those ideas with cited answers. The currently implied primary user is a single self-hosting operator: the repo emphasizes easy single-user self-hosting, a lightweight default path, contributor-friendly docs, and manual capture before richer platform connectors. Evidence: `README.md` lines 3-10, `docs/specs/initial-product-spec.md` lines 3-14, and `docs/self-hosting.md` lines 3-21.

The product should not become an API-key-only hosted-AI wrapper. Local AI, OpenAI-compatible endpoints, OAuth/device login, Codex-style flows, Hermes/proxy flows, and static/env credentials must all remain possible through provider/credential abstractions. Evidence: `README.md` lines 7-10, `AGENTS.md` lines 11-12, `docs/providers.md` lines 5-30, and `docs/decisions/ADR-004-credential-providers.md` lines 6-17.

## Current implementation status

The repository is still at initialization/skeleton stage. `README.md` says implementation is being initialized, `CHANGELOG.md` only lists initial documentation and development standards, and the CLI currently prints `idea-inbox: implementation pending`. The current baseline tests only verify package version metadata and the configured CLI callable. Evidence: `README.md` lines 22-39, `CHANGELOG.md` lines 7-11, `src/idea_inbox/cli.py` lines 1-2, and `tests/test_package_baseline.py` lines 14-26.

`pyproject.toml` defines a Python 3.11+ package named `idea-inbox`, an `idea-inbox` console script at `idea_inbox.cli:main`, no runtime dependencies yet, and dev dependencies on `pytest` and `ruff`. Evidence: `pyproject.toml` lines 1-28.

## Confirmed decisions

1. Stable extension boundaries exist from the beginning.
   - Accepted decision: define stable interfaces for connectors, model providers, embedding providers, credential providers, search indexes, and storage backends. Evidence: `docs/decisions/ADR-001-connector-and-provider-boundaries.md` lines 10-18.
   - Contributor standard: new platforms/providers should be modules, not rewrites; core domain code must not import provider SDK types; route handlers should stay thin; dependency injection is preferred over global clients. Evidence: `CONTRIBUTING.md` lines 32-50.

2. Raw events are stored before normalized ideas.
   - Accepted decision: every external message is first stored as a raw event; normalized ideas are derived records that can be regenerated. Evidence: `docs/decisions/ADR-005-raw-events-derived-ideas.md` lines 10-18.
   - Architecture flow: `External source → Connector → RawEvent → IdeaDraft → Idea → Indexes → Query → Cited answer`. Evidence: `docs/architecture.md` lines 5-9.
   - Agent non-negotiable: preserve raw events before normalizing ideas. Evidence: `AGENTS.md` lines 7-10.

3. Retrieval answers must be citation-backed.
   - Accepted decision: generated query answers must cite the ideas used as evidence, and if no relevant ideas are found the assistant must say so. Evidence: `docs/decisions/ADR-003-cited-retrieval-answers.md` lines 10-18.
   - Testing standard: query tests must verify citations. Evidence: `CONTRIBUTING.md` lines 62-68.

4. SQLite is the default lightweight/dev storage path; Postgres + pgvector is optional for production.
   - Accepted decision: use SQLite as default and maintain optional Postgres + pgvector production profile. Evidence: `docs/decisions/ADR-002-sqlite-default-postgres-production.md` lines 10-18.
   - README and self-hosting docs repeat the lightweight SQLite default and Docker/Docker Compose self-host path. Evidence: `README.md` lines 31-39 and `docs/self-hosting.md` lines 3-21.

5. Credential providers are a first-class boundary.
   - Accepted decision: model providers obtain secrets through credential providers; MVP can ship env/static providers, but contracts must allow device login, OAuth refresh, and local proxy providers later. Evidence: `docs/decisions/ADR-004-credential-providers.md` lines 10-17.
   - Initial provider docs list `none`, `env_api_key`, and `static_config` as initial credential providers, with `oauth_device_code`, `codex_login`, `hermes_proxy`, and `browser_login` as future providers. Evidence: `docs/providers.md` lines 15-30.

6. Development uses spec-first and TDD gates.
   - Workflow: `SPEC → PLAN → TASKS → TEST → IMPLEMENT → VERIFY → REVIEW → COMMIT`. Evidence: `CONTRIBUTING.md` lines 5-19.
   - Behavior changes require RED/GREEN/REFACTOR TDD, deterministic provider mocks, no real platform calls in normal tests, and regression tests before bug fixes. Evidence: `CONTRIBUTING.md` lines 52-68.
   - Done requires met acceptance criteria, passing tests/lint/type checks, docs updates when needed, ADR updates for architecture changes, and a summary of touched vs. intentionally untouched work. Evidence: `CONTRIBUTING.md` lines 109-119.

7. Public API standards are already constrained.
   - Versioned REST endpoints live under `/v1`; request/response schemas use Pydantic; errors follow a consistent `error.code/message/details` shape; list endpoints are paginated from day one; third-party webhook payloads are validated at the boundary. Evidence: `CONTRIBUTING.md` lines 70-88.

## Architectural assumptions to preserve in the MVP spec

- Core domain vocabulary: `RawEvent`, `IdeaDraft`, `Idea`, `Connector`, `ModelProvider`, `EmbeddingProvider`, `CredentialProvider`, `SearchIndex`, and `StorageBackend`. Evidence: `docs/architecture.md` lines 11-21.
- Connector contract: validate provider payloads at the boundary, preserve provider IDs for idempotency, map provider payloads to `RawEvent`, extract zero or more `IdeaDraft` records, and prevent provider SDK types from leaking into core modules. Evidence: `docs/connectors.md` lines 5-14.
- Planned connector order/scope: manual API, generic webhook, Telegram, Email/IMAP, Discord, and later WhatsApp Cloud API. Unofficial account-scraping connectors are not allowed in core. Evidence: `docs/connectors.md` lines 15-24.
- Model/embedding provider starting points: mock provider for tests, OpenAI-compatible HTTP provider, Ollama/local provider, local sentence-transformer embeddings, and later OAuth/proxy/Codex-style credential flows. Evidence: `docs/providers.md` lines 5-13.
- Configuration surface currently anticipates SQLite database URL, log level, mock chat/embedding providers, OpenAI-compatible base URL/model names/API key, manual API key, Telegram/Discord tokens, and email IMAP credentials. Evidence: `.env.example` lines 1-20.
- Deployment assumptions: local lightweight mode should run with SQLite, built-in API, and mock/local providers; recommended production should use Docker Compose with Postgres + pgvector; paid hosted models must not be required. Evidence: `docs/self-hosting.md` lines 3-21.

## Known MVP phase ideas

The most complete phase list is in the initial product spec:

1. Project skeleton and standards.
2. Manual idea API.
3. Raw event pipeline.
4. Keyword search.
5. Cited query endpoint.
6. Embeddings and hybrid search.
7. Telegram/email/Discord connectors.
8. Optional Postgres + pgvector deployment profile.

Evidence: `docs/specs/initial-product-spec.md` lines 16-25. The README planned MVP is similar but condenses the sequence to manual API capture, raw event ingestion, SQLite + FTS, provider interfaces, cited query endpoint, Telegram/email/Discord connectors, and optional Postgres + pgvector. Evidence: `README.md` lines 12-20.

## Explicitly out of scope for MVP

- Full web app UI.
- Multi-user permissions.
- Unofficial WhatsApp scraping.
- Complex autonomous workflows.

Evidence: `docs/specs/initial-product-spec.md` lines 27-32 and `docs/connectors.md` lines 22-24.

## Inventory questions and MVP spec resolutions

1. API surface details needed specification.
   - Resolved by `mvp-architecture-spec.md`: manual capture uses `POST /v1/ideas`, generic connector ingestion uses `POST /v1/connectors/{connector_name}/events`, search uses `GET /v1/ideas/search`, query uses `POST /v1/query`, and responses follow `/v1`, pagination, citation, idempotency, and standard error-shape requirements.

2. Raw event and idea schema details needed specification.
   - Resolved by `mvp-architecture-spec.md`: required `RawEvent`, `IdeaDraft`, `Idea`, `SearchHit`, and `Citation` fields are named, raw events remain the source lineage record, and SQLite migrations are required for deterministic local storage.

3. Search backend sequencing needed reconciliation.
   - Resolved by `mvp-architecture-spec.md`: keyword/FTS search and cited query behavior come before optional embeddings/hybrid search, so citations are supported initially by stored ideas retrieved through SQLite FTS.

4. Provider interface contracts needed definition.
   - Resolved for MVP planning by `mvp-architecture-spec.md`: `ModelProvider`, `EmbeddingProvider`, and `CredentialProvider` protocol shapes are named, mocks are required for tests, and retries/timeouts/configuration remain explicit adapter concerns.

5. Connector authentication and verification behavior needed clarification.
   - Resolved for MVP planning by `mvp-architecture-spec.md`: connector modules validate payloads at the boundary, preserve provider IDs, use connector-specific credential providers, keep retries/polling configurable, and start fixture-driven before real platform calls.

6. Storage abstraction scope needed a first-slice boundary.
   - Resolved by `mvp-architecture-spec.md`: SQLite is the first concrete storage/search path behind `StorageBackend` and `SearchIndex`; Postgres + pgvector stays optional after SQLite is healthy, with opt-in integration tests.

7. Self-hosting commands are aspirational until implementation exists.
   - Resolved by `mvp-architecture-spec.md` and current README/self-hosting docs: the current smoke command is `uv run idea-inbox`; planned commands such as `idea-inbox dev`, `idea-inbox migrate`, and `idea-inbox serve` must stay labeled as target commands until implemented and tested.

8. Docs mention Docker and Compose as planned production paths before files exist.
   - Resolved by `mvp-architecture-spec.md` and current README/self-hosting docs: Docker and Compose remain planned deployment targets only until the repository includes matching assets such as a Dockerfile, Compose file, and/or confirmed published image.

9. Multi-user and permission boundaries needed explicit deferral.
   - Resolved by `mvp-architecture-spec.md` and ADR-006: multi-user ownership is out of scope; any future-proof fields must be nullable metadata or single-operator placeholders, not implicit security boundaries.

## Recommended handoff focus for the full MVP spec worker

Start by turning the confirmed decisions above into acceptance criteria for the first executable slice: manual `/v1` idea capture into SQLite, preserving raw input as `RawEvent`, deriving an `Idea`, supporting keyword retrieval, and returning query answers with citations using a deterministic mock provider. Keep connector/provider interfaces narrow but explicit enough that Telegram/email/Discord, local AI, OpenAI-compatible providers, and future credential providers can be added without changing core domain contracts.
