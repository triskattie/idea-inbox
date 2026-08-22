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

The privacy-preserving default development path must not require hosted-model credentials, hidden
outbound model calls, local model daemons, connector tokens, vector databases, or telemetry. The
v0.2.0 cited-query foundation and Phase 7 provider-adapter boundaries are present, but query and
provider capabilities remain disabled by default for normal `dev` and `serve` runs. Provider-backed
query is currently limited to explicit in-process tests or embedded harnesses.

The WSGI API app is available as `idea_inbox.api.create_app`, and the CLI server wrapper starts
it after applying pending SQLite migrations. It currently exposes:

- `POST /v1/ideas` for manual idea capture. The endpoint validates and normalizes the JSON body,
  stores a `manual` raw event first, then persists the derived draft and canonical idea.
- `GET /v1/ideas/search?q=...&limit=10` for SQLite FTS-backed search over stored ideas.
- `POST /v1/query` for cited answers when the optional `query-ai` capability is enabled.
  The public `dev`/`serve` path uses the default registry, so `query-ai` is disabled and the route
  returns `503 CAPABILITY_DISABLED` without request validation, retrieval, provider startup, or
  outbound network work. Embedded deterministic/mock harnesses can enable it by supplying provider
  capability metadata, explicit enabled overrides, and an injected model provider to
  `create_app(...)`; no hosted model credentials or provider SDKs are required for those smoke tests.

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
fails before migrations run.

## Optional Postgres + pgvector profile

SQLite stays the default dev path. An optional Postgres profile exists for self-hosters who want
a server database (and the pgvector extension for a future embeddings phase):

1. Start the database: `docker compose --profile postgres up -d` (uses the `pgvector/pgvector:pg16`
   image, bound to `127.0.0.1:5434`).
2. Install the optional driver: `pip install -e '.[postgres]'` (or
   `uv sync --extra postgres`).
3. Point Idea Inbox at it: `IDEA_INBOX_DATABASE_URL=postgresql://idea_inbox:idea_inbox@127.0.0.1:5434/idea_inbox`.

`idea-inbox migrate` applies the same deterministic migration model to Postgres
(`src/idea_inbox/storage/postgres_migrations/`). The `PostgresStorageBackend` and
`PostgresFTSSearchIndex` implement the same service contracts as the SQLite backend, so manual
capture, connector ingestion, keyword search, and cited query behave identically. Postgres
integration tests are opt-in and never run in the normal suite; see
`tests/test_postgres_integration.py` for the exact command.

The current runtime also loads `IDEA_INBOX_ENV` and `IDEA_INBOX_LOG_LEVEL`. Provider keys in
`.env.example` describe the Phase 7 opt-in adapter surface, but they do not change normal
`dev`/`serve` startup because those commands do not install or enable provider capabilities. The
connector and API-token-looking keys remain planned no-ops. In particular, setting
`IDEA_INBOX_API_KEY` does not protect `POST /v1/ideas` yet; bind to `127.0.0.1` or add your own
reverse proxy, network ACL, or access-control layer before exposing `dev` or `serve` beyond the
local host.

## Optional connectors

Phase 8 connector adapters are offline fixture parsers plus one capability-gated HTTP route. None
of them are enabled by default, and none of them poll platforms or read connector credentials.

- Generic webhook: `POST /v1/connectors/webhook/generic` returns `503 CAPABILITY_DISABLED` until
  the built-in `generic-webhook-connector` capability is enabled. There is no env flag for this
  yet; enablement happens through an injected `CapabilityRegistry`, for example
  `create_app(database_path=..., capability_registry=CapabilityRegistry(enabled_overrides={"generic-webhook-connector": True}))`.
  Accepted bodies are JSON objects with required non-empty `text` and optional `event_id`
  (preserved verbatim as the idempotency key), `source_ref`, `actor_ref`, `occurred_at`,
  `metadata`, and `tags`.
- Telegram, email, and Discord adapters (`idea_inbox.connectors.telegram.TelegramConnector`,
  `idea_inbox.connectors.email.EmailConnector`,
  `idea_inbox.connectors.discord.DiscordConnector`) parse payloads/fixtures in-process only;
  there are no polling runtimes, bot tokens, or IMAP connections yet, and their `.env.example`
  keys stay reserved no-ops.

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
  JSON object with required non-empty `text` plus optional `idempotency_key`, `source_ref`,
  `actor_ref`, `captured_at`, `metadata`, and `tags`. It stores a `manual` raw event before the
  derived draft and canonical idea, then returns `201 Created` with the created `item`.
- Search currently runs through the same API at `GET /v1/ideas/search?q=...&limit=10`.
- The CLI `dev` and `serve` commands apply pending SQLite migrations, bind the configured host
  and port, and serve the `/v1` API until stopped. Deployment packaging still needs a Dockerfile,
  Compose file, or service unit before this is a turnkey production artifact.

MVP exposure notes:

- Bind to `127.0.0.1` unless you have deliberately put your own reverse proxy, network ACL, or
  other access control in front of the process. The manual API does not yet enforce an
  application-level access token.
- Replayed manual `POST /v1/ideas` requests are idempotent by `idempotency_key` when supplied, or
  by a dedupe key derived from the normalized request body when no key is supplied.


## Cited query capability

`POST /v1/query` is available in the WSGI route table, but self-hosted operators should treat it as
a default-disabled v0.2.0 foundation. The built-in `query-ai` capability has
`default_enabled=False` and depends on `sqlite-fts-search`, `model-provider`, and
`IDEA_INBOX_CHAT_PROVIDER` when enabled. Normal CLI startup does not install a model-provider
capability or apply an enabled override, so this curl works as a safe disabled-path smoke test and
does not need model credentials:

```bash
curl -i -X POST http://127.0.0.1:8080/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"What ideas did I save about local AI?"}'
```

Expected default response: `503 Service Unavailable` with `error.code == "CAPABILITY_DISABLED"`,
`error.details.capability == "query-ai"`, and `error.details.status == "disabled"`. The disabled
path exits before request validation, SQLite retrieval, model-provider setup, or outbound network
calls.

Current enable/disable surface:

- Disable: use the default `CapabilityRegistry()`, omit a `query-ai` override, or explicitly pass
  `enabled_overrides={"query-ai": False}` in an embedded/test harness. This is what `dev` and
  `serve` do today.
- Enable for deterministic local tests only: construct the WSGI app with provider metadata from
  `idea_inbox.providers.capabilities.provider_capabilities()`, set `enabled_overrides` for
  `query-ai`, `model-provider`, `mock-model-provider`, and `none-credentials`, provide
  `config_values={"IDEA_INBOX_CHAT_PROVIDER": "mock"}`, and inject a `MockModelProvider` if you
  want the model-provider boundary exercised explicitly. The canonical example is
  `tests/test_api_query.py::deterministic_query_registry`.
- Implemented but still harness-only: OpenAI-compatible and Ollama provider adapters can map stored
  evidence to `/chat/completions` and `/api/generate` request payloads with fakeable HTTP boundaries.
  Normal tests fake those boundaries and do not call hosted APIs or an Ollama daemon.
- Not implemented yet: a CLI flag, `.env` toggle, provider package discovery, automatic provider
  construction from environment, streaming, embeddings/vector or hybrid search, public query UI, or
  production auth. Setting `IDEA_INBOX_CHAT_PROVIDER=mock` in `.env` alone does not enable query for
  the packaged server.

When enabled by a harness, query only answers from stored ideas in the configured SQLite database.
It is not general web search, does not ingest connector data, does not read raw event payload bodies
as answer text, and returns a no-evidence response instead of fabricating an answer when FTS finds
nothing relevant. Keep `dev`/`serve` bound to `127.0.0.1` or reachable only through a private
network such as Tailscale unless you add your own authentication and network controls.

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

The intended lightweight self-host path is the current SQLite-backed WSGI API packaged for a
single host. Optional modules can add public provider enablement, richer AI-assisted query,
connectors, embeddings, or deployment profiles, but the base self-host path should remain capture +
SQLite search with default-disabled query and no mandatory AI. A Docker image may become the
convenient packaging format once the repository includes a Dockerfile and a published image exists.

## Planned production self-hosting

The intended production profile is Docker Compose with Postgres + pgvector and explicit
provider configuration. Do not use Docker or Compose commands from this documentation until
matching repository assets exist, such as a `Dockerfile`, a Compose file, and/or a confirmed
published image.

No production setup should require a paid hosted model. Hosted models may be optional accelerators.
