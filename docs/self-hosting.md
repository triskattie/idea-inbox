# Self-hosting

Target deployment modes, separated by what is available now versus what is planned.

## Current local development path

The current self-hosting baseline is a local SQLite database plus a runnable WSGI API. The
top-level CLI command verifies that the package entry point works, `idea-inbox migrate` applies
the real SQLite schema and FTS migrations, and `idea-inbox dev`/`idea-inbox serve` start the
local API process.

```bash
uv sync
cp .env.example .env
uv run idea-inbox
uv run idea-inbox migrate
uv run idea-inbox dev --host 127.0.0.1 --port 8080
```

Local/mock mode is the privacy-preserving default for development: it must not require
hosted-model credentials, hidden outbound model calls, or telemetry. Hosted model providers may
be configured explicitly later, but they are optional accelerators rather than a requirement for
local development.

The WSGI API app is available as `idea_inbox.api.create_app`, and the CLI server wrapper starts
it after applying pending SQLite migrations. It currently exposes:

- `POST /v1/ideas` for manual idea capture. The endpoint validates and normalizes the JSON body,
  stores a `manual` raw event first, then persists the derived draft and canonical idea.
- `GET /v1/ideas/search?q=...&limit=10` for SQLite FTS-backed search over stored ideas.

`dev` is the local development entrypoint. `serve` exposes the same API with explicit host/port
options for local or self-hosted use. Production packaging still needs a Dockerfile, Compose file,
or service-unit wrapper before this is a turnkey deployment artifact.

## SQLite configuration

SQLite is the current implemented persistence backend. By default, Idea Inbox uses
`sqlite:///./data/idea-inbox.sqlite3`, resolved relative to the directory where the CLI process
is started. The repository template stores that value in `.env.example` as
`IDEA_INBOX_DATABASE_URL`.

Use one database location setting at a time:

- `IDEA_INBOX_DATABASE_URL=sqlite:///./data/idea-inbox.sqlite3` for a SQLite URL.
- `IDEA_INBOX_DATABASE_URL=sqlite+aiosqlite:///./data/idea-inbox.sqlite3` if a future async
  caller needs the SQLAlchemy-style SQLite URL form; the current storage path still resolves it
  to the same local file.
- `IDEA_INBOX_SQLITE_PATH=./data/idea-inbox.sqlite3` for a plain path.

If `IDEA_INBOX_DATABASE_URL` and `IDEA_INBOX_SQLITE_PATH` are both set, configuration loading
fails before migrations run. The MVP backend rejects non-SQLite URLs such as Postgres until a
separate Postgres storage adapter is implemented.

The current runtime also loads `IDEA_INBOX_ENV` and `IDEA_INBOX_LOG_LEVEL`. Provider, connector,
and API-token-looking keys in `.env.example` are reserved for planned work and are not enforced by
today's WSGI API. In particular, setting `IDEA_INBOX_API_KEY` does not protect `POST /v1/ideas`
yet; bind to `127.0.0.1` or add your own reverse proxy, network ACL, or access-control layer
before exposing `dev` or `serve` beyond the local host.

## Current SQLite migrations and search index

SQLite is the current runnable persistence path. Apply migrations with:

```bash
uv run idea-inbox migrate
```

Use `uv run idea-inbox migrate --database ./path/to/ideas.sqlite3` to migrate a specific
database file instead of the configured `IDEA_INBOX_DATABASE_URL` / `IDEA_INBOX_SQLITE_PATH`.
Migrations create parent directories for file-backed databases before opening SQLite.

The migration runner creates `schema_migrations`, then applies numbered SQL files from
`src/idea_inbox/storage/migrations/` in filename order. Migration checksums are recorded in `schema_migrations`.
If an already-applied migration's name or checksum changes, migration stops with an error
instead of silently continuing. Re-running `uv run idea-inbox migrate` is expected to be a no-op
after the current migration set has been applied.

Current migration files:

- `0001_initial_storage.sql` creates authoritative `raw_events`, `idea_drafts`, `ideas`, and
  `idea_tags` tables and supporting indexes.
- `0002_idea_fts.sql` creates the `idea_fts` SQLite FTS5 projection over canonical ideas and
  finishes with an FTS rebuild so existing `ideas` rows become searchable.

Operational notes:

- The Python `sqlite3` build must include SQLite FTS5. If it does not, migration fails before
  applying the FTS migration with `SQLite FTS5 is not available in this Python sqlite3 build`.
- `idea_fts` is a derived projection, not the authoritative store. It can be rebuilt from the
  `ideas` table with `SQLiteFTSSearchIndex(storage).rebuild()` if the projection is cleared or
  suspected stale.
- The projection is kept synchronized by SQLite triggers on `ideas` insert, update, and delete.
  Raw events remain stored even when a derived idea is deleted.
- Manual capture currently runs through the WSGI API at `POST /v1/ideas`; the endpoint accepts a
  JSON object with required non-empty `text` plus optional `source_ref`, `actor_ref`,
  `captured_at`, `metadata`, and `tags`. It stores a `manual` raw event before the derived draft
  and canonical idea, then returns `201 Created` with the created `item`.
- Search currently runs through the same API at `GET /v1/ideas/search?q=...&limit=10`.
- The CLI `dev` and `serve` commands apply pending SQLite migrations, bind the configured host
  and port, and serve the `/v1` API until stopped. Deployment packaging still needs a Dockerfile,
  Compose file, or service unit before this is a turnkey production artifact.

MVP exposure notes:

- Bind to `127.0.0.1` unless you have deliberately put your own reverse proxy, network ACL, or
  other access control in front of the process. The manual API does not yet enforce an
  application-level access token.
- Replayed manual `POST /v1/ideas` requests currently create new raw events and ideas; the
  planned source/idempotency-key replay behavior has not landed yet.

## Resetting a local development database

For disposable local development data, stop any running Idea Inbox process, delete the
configured `.sqlite3` file and run migrations again:

```bash
rm -f data/idea-inbox.sqlite3
uv run idea-inbox migrate
```

If you use a custom path, delete that file instead. Do not use this as an upgrade procedure for
real self-hosted data: raw events are the audit/reprocessing source, and deleting the database
removes the raw-event trail, drafts, ideas, tags, and search projection together.

## Planned lightweight self-hosting

The intended lightweight self-host path is the current SQLite-backed WSGI API plus mock or local
providers packaged for a single host. A Docker image may become the convenient packaging format
once the repository includes a Dockerfile and a published image exists.

## Planned production self-hosting

The intended production profile is Docker Compose with Postgres + pgvector and explicit
provider configuration. Do not use Docker or Compose commands from this documentation until
matching repository assets exist, such as a `Dockerfile`, a Compose file, and/or a confirmed
published image.

No production setup should require a paid hosted model. Hosted models may be optional accelerators.
