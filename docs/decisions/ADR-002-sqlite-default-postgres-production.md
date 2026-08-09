# ADR-002: SQLite default and Postgres production profile

## Status
Accepted

## Context

The project should be easy to deploy and contribute to, while still allowing a stronger production path.

## Decision

Use SQLite as the default lightweight/dev path. Maintain an optional Postgres + pgvector production profile.

## Consequences

- New users can try the app without operating a database service.
- Production users can choose Postgres for backups, concurrency, and pgvector.
- Storage/search boundaries must be tested against both paths once Postgres support lands.
