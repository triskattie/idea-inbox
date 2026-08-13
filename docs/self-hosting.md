# Self-hosting

Target deployment modes, separated by what is available now versus what is planned.

## Current local smoke setup

The repository is currently in initialization. The available local path is a smoke setup
that installs the package and runs the placeholder CLI with SQLite-oriented configuration
and mock/local providers.

```bash
uv sync
cp .env.example .env
uv run idea-inbox
```

Local/mock mode is the privacy-preserving default for development: it must not require
hosted-model credentials, hidden outbound model calls, or telemetry. Hosted model providers
may be configured explicitly later, but they are optional accelerators rather than a
requirement for local development.

## Current SQLite migrations and search index

SQLite is the current runnable persistence path. Apply migrations with:

```bash
uv run idea-inbox migrate
```

Use `uv run idea-inbox migrate --database ./path/to/ideas.sqlite3` to migrate a specific
database file instead of the configured `IDEA_INBOX_DATABASE_URL` / `IDEA_INBOX_SQLITE_PATH`.
Migration `0002_idea_fts.sql` creates the `idea_fts` SQLite FTS5 projection over canonical
ideas and finishes with an FTS rebuild so existing `ideas` rows become searchable.

Operational notes:

- The Python `sqlite3` build must include SQLite FTS5. If it does not, migration fails before
  applying the FTS migration with `SQLite FTS5 is not available in this Python sqlite3 build`.
- `idea_fts` is a derived projection, not the authoritative store. It can be rebuilt from the
  `ideas` table with `SQLiteFTSSearchIndex(storage).rebuild()` if the projection is cleared or
  suspected stale.
- The projection is kept synchronized by SQLite triggers on `ideas` insert, update, and delete.
  Raw events remain stored even when a derived idea is deleted.
- Search currently runs through the importable WSGI app at `GET /v1/ideas/search?q=...&limit=10`.
  The CLI `serve` command still parses options but does not start an HTTP server yet, so
  deployment packaging still needs a server entrypoint around `idea_inbox.api.create_app`.

## Planned lightweight self-hosting

The intended lightweight self-host path is SQLite, the built-in API, and mock or local
providers packaged for a single host. A Docker image may become the convenient packaging
format once the repository includes a Dockerfile and a published image exists.

## Planned production self-hosting

The intended production profile is Docker Compose with Postgres + pgvector and explicit
provider configuration. Do not use Docker or Compose commands from this documentation until
matching repository assets exist, such as a `Dockerfile`, a Compose file, and/or a confirmed
published image.

No production setup should require a paid hosted model. Hosted models may be optional accelerators.
