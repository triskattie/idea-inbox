# Changelog

All notable changes to Idea Inbox will be documented here.

The format follows Keep a Changelog-style sections: Added, Changed, Deprecated, Removed, Fixed, Security.

## [0.2.0] - 2026-08-22

### Added

- Default-disabled cited-query foundation at `POST /v1/query`, guarded by the built-in `query-ai`
  capability and returning `503 CAPABILITY_DISABLED` in normal local `dev`/`serve` runs.
- Deterministic local/mock query behavior for tests and embedded harnesses: SQLite FTS retrieval,
  storage-backed citation resolution, evidence-backed answers, and explicit no-evidence responses.
- Cited-query API contract documentation covering request validation, success/no-evidence/error
  response shapes, citation/provenance requirements, and fabrication rules.

### Changed

- Capability documentation now names `query-ai` as a built-in query capability that is present but
  disabled by default, with enablement limited to explicit in-process registry overrides for the
  v0.2.0 foundation.
- Self-hosting docs now describe the safe default disabled query path and localhost/private-network
  exposure assumptions.

### Deferred

- General web search, connector ingestion, embeddings/vector or hybrid search, real hosted/local
  provider adapters, provider package discovery, streaming, UI, production auth, multi-user
  ownership, and public internet exposure remain outside v0.2.0.

## [0.1.0] - 2026-08-16

### Added

- Initial local manual capture and search MVP release.
- CLI smoke, `dev`, `migrate`, and `serve` commands, including implemented SQLite migration
  execution through `idea-inbox migrate` and runnable `dev`/`serve` WSGI API startup.
- SQLite configuration, deterministic migrations, durable raw event/draft/idea storage, and the
  rebuildable FTS5 search projection.
- WSGI API endpoints for manual capture and FTS-backed idea search.
- Manual idea capture through `POST /v1/ideas`, preserving a raw event before derived idea
  records and normalizing tags, metadata, and source fields.
- Source-scoped manual capture idempotency via optional `idempotency_key` and normalized request
  hash fallback.
- Documentation for local setup, manual capture, search, self-hosting boundaries, and reserved
  provider/connector environment settings.

### Deferred

- Cited natural-language query answers, model/provider adapters, platform connectors, and optional
  Postgres/pgvector deployment profiles are planned for later milestones after this first local
  capture/search release.
