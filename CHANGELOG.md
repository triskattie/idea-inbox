# Changelog

All notable changes to Idea Inbox will be documented here.

The format follows Keep a Changelog-style sections: Added, Changed, Deprecated, Removed, Fixed, Security.

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
