# ADR-002: SQLite default and Postgres production profile

## Status
Accepted

## Context

The project should be easy to deploy and contribute to, while still allowing a stronger production path. The MVP architecture spec requires SQLite as the default storage backend, SQLite FTS for the first query-capable search slice, and optional Postgres + pgvector only after the SQLite path is healthy.

See [`../specs/mvp-architecture-spec.md`](../specs/mvp-architecture-spec.md), especially the storage design, search design, self-hosting assumptions, and Phase 8 acceptance criteria.

## Decision

Use SQLite as the default lightweight/dev path. Maintain an optional Postgres + pgvector production profile.

`StorageBackend` remains authoritative for stored raw events, drafts, canonical ideas, and citation lineage. Search implementations, including SQLite FTS, pgvector, or hybrid indexes, are derived projections that can be rebuilt from storage.

The first MVP search implementation is SQLite FTS over canonical `Idea` records. Embeddings, vector search, and hybrid ranking remain behind `SearchIndex` and `EmbeddingProvider` contracts and are added only after FTS search and citation behavior are tested.

## Consequences

- New users can try the app without operating a database service.
- Production users can choose Postgres for backups, concurrency, and pgvector.
- Storage/search boundaries must be tested against both paths once Postgres support lands.
- Query paths must resolve ranked search hits back to stored ideas before generating cited answers.
- Normal tests should run against temporary SQLite databases; Postgres/vector integration tests are opt-in until the production profile is implemented.
