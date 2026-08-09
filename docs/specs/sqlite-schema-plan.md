# SQLite schema plan

## Status

Planning note for the first SQLite storage foundation. This document narrows the storage design in `mvp-architecture-spec.md` into concrete tables and migration ordering before implementation.

## Source context

This plan maps the current repository touchpoints documented in:

- `src/idea_inbox/cli.py` for the planned `idea-inbox migrate`, `idea-inbox dev`, and `idea-inbox serve` commands.
- `.env.example` for the current configuration surface, especially `IDEA_INBOX_DATABASE_URL`, provider selectors, provider model settings, and connector secrets.
- `docs/architecture.md` for the mandatory `RawEvent -> IdeaDraft -> Idea -> Indexes -> Query -> Cited answer` flow.
- `docs/connectors.md` for connector idempotency and raw-payload preservation.
- `docs/providers.md` and ADR-004 for credential-provider boundaries.
- ADR-002, ADR-003, and ADR-005 for SQLite-first storage, cited retrieval, and raw-event preservation.

## Current persistence and configuration touchpoints

The implementation is still a package and CLI skeleton, so there are no runtime storage modules yet. The persistence/configuration touchpoints that the first SQLite implementation must connect are:

- CLI startup and migration commands: `idea-inbox migrate` applies deterministic migrations for the backend selected by configuration; `idea-inbox dev` and `idea-inbox serve` should verify or apply the same SQLite foundation before accepting writes.
- Database selection: `IDEA_INBOX_DATABASE_URL` points at the local SQLite database in development (`sqlite+aiosqlite:///./data/idea-inbox.sqlite3`). It selects storage location/driver, not application data.
- Connector input: manual API, generic webhooks, Telegram, email/IMAP, and Discord need source names, provider event IDs, idempotency keys, actor/source references, raw payloads, and provider timestamps preserved before extraction.
- Query evidence: search and generated answers need stable idea IDs, idea text, capture timestamps, source metadata, snippets, scores, and lineage back to raw events.
- Provider configuration: chat/embedding provider choices, base URLs, model names, and credential-provider references are application configuration. Configuration stays outside SQLite for the first foundation unless a later spec creates a non-secret settings table.
- Secrets: API keys, bot tokens, email passwords, OAuth tokens, local browser sessions, and proxy credentials remain behind `CredentialProvider` implementations. Secrets must not be migrated into SQLite by the storage foundation.

## Tables

### `schema_migrations`

Tracks deterministic migration application.

- Primary key: `version` text, matching the migration filename prefix.
- Columns: `version`, `name`, `checksum`, `applied_at`.
- Indexes: primary key on `version`; unique `checksum` is optional but useful for detecting accidental duplicate files.
- Timestamps: `applied_at` is set by the migration runner when a file succeeds.
- Mapping: there is no existing persisted data. This table backs the planned `idea-inbox migrate` command and lets dev/server startup prove the schema is current.

### `raw_events`

Authoritative store for original connector/provider input.

- Primary key: `id` text, generated internally with a stable prefix such as `raw_`.
- Columns: `id`, `source`, `provider_event_id`, `dedupe_key`, `received_at`, `occurred_at`, `actor_ref`, `payload`, `payload_hash`, `processing_state`, `error_code`, `error_message`, `created_at`, `updated_at`.
- Indexes: unique `(source, dedupe_key)` for idempotent ingestion; non-unique `(source, provider_event_id)` for provider lookup; non-unique `processing_state` for retry/reprocessing scans; non-unique `received_at` for auditing and pagination.
- Timestamps: `received_at` records when Idea Inbox accepted the event; `occurred_at` records provider time when available; `created_at` and `updated_at` track the local row lifecycle.
- Mapping: Connector raw payloads from manual API submissions, generic webhooks, Telegram, email, and Discord become `payload` before any draft extraction. `source` is the connector name. Provider message IDs map to `provider_event_id`. Idempotency headers or provider IDs map to `dedupe_key`. Sender/channel/mailbox references map to `actor_ref` or payload metadata, not separate account tables in the MVP.

### `idea_drafts`

Stores normalized candidates extracted from raw events before canonical idea persistence.

- Primary key: `id` text, generated internally with a stable prefix such as `draft_`.
- Columns: `id`, `raw_event_id`, `text`, `source_created_at`, `source_uri`, `metadata`, `extraction_state`, `created_at`, `updated_at`.
- Indexes: non-unique `raw_event_id`; non-unique `extraction_state`; optional unique `(raw_event_id, text)` only if extraction is deterministic enough to avoid false duplicate suppression.
- Timestamps: `source_created_at` preserves source/provider time for the draft; `created_at` and `updated_at` track local extraction lifecycle.
- Mapping: `Connector.extract_drafts(raw_event)` output is stored here so connector changes can be audited and re-run from raw events. Manual capture normally creates one draft with the submitted text. A webhook or chat message may create zero, one, or multiple drafts.

### `ideas`

Canonical searchable ideas that query answers may cite.

- Primary key: `id` text, generated internally with a stable prefix such as `idea_`.
- Columns: `id`, `raw_event_id`, `draft_id`, `text`, `source`, `source_ref`, `captured_at`, `metadata`, `embedding_state`, `created_at`, `updated_at`, `deleted_at`.
- Indexes: non-unique `raw_event_id`; non-unique `draft_id`; non-unique `(source, source_ref)` for source filtering; non-unique `captured_at` for pagination and time filters; non-unique `embedding_state` for embedding backfill scans.
- Timestamps: `captured_at` is provider time when available, otherwise ingest time; `created_at` and `updated_at` are local row timestamps; `deleted_at` enables soft deletion without breaking citation/audit lineage.
- Mapping: Canonical `Idea` records are derived from `idea_drafts`. Generated answers cite these rows by `id`; citations resolve through `raw_event_id` and `draft_id` rather than citing FTS fragments alone. Tags can be copied into `metadata` and normalized into `idea_tags` when filtering is needed.

### `idea_tags`

Normalized tag/filter projection for canonical ideas.

- Primary key: composite `(idea_id, tag)`.
- Columns: `idea_id`, `tag`, `created_at`.
- Indexes: primary key `(idea_id, tag)`; non-unique `tag` for tag filters.
- Timestamps: `created_at` records when the tag projection was created.
- Mapping: If an idea draft or future enrichment supplies tags, each normalized tag is inserted here while the original tag list remains in `ideas.metadata`. This keeps filtering/query UX simple without making tags a separate user-owned taxonomy in the MVP.

### `idea_fts`

SQLite FTS virtual table for keyword search over canonical ideas.

- Primary key: use the FTS rowid mapped to the canonical `ideas` row or an unindexed `idea_id` column, depending on the SQLite FTS implementation chosen during storage work.
- Columns: `text`, `source`, `tags`, and/or `metadata_text` as indexed content, plus an unindexed stable idea reference when needed.
- Indexes: FTS tables own their search index; the implementation should keep an ordinary lookup path back to `ideas.id`.
- Timestamps: no authoritative timestamps; all time data remains in `ideas` and is joined/resolved from storage.
- Mapping: `SearchIndex.upsert_idea(idea)` writes this derived projection from `ideas`, not from raw events. It can be rebuilt from `ideas` at any time and must not become the only store for idea text or citation lineage.

### `embeddings`

Deferred but reserved table for local/hybrid search once FTS and cited query behavior are working.

- Primary key: composite `(idea_id, provider_id, model, dimensions)` or a generated `id` plus a unique equivalent index.
- Columns: `id`, `idea_id`, `provider_id`, `model`, `dimensions`, `vector`, `vector_format`, `created_at`, `updated_at`.
- Indexes: unique `(idea_id, provider_id, model, dimensions)`; non-unique `(provider_id, model)` for backfills.
- Timestamps: `created_at` records first embedding; `updated_at` records refresh when provider/model/vector format changes.
- Mapping: `EmbeddingProvider` output for stored `ideas` lands here after the required SQLite FTS slice. For SQLite, `vector` can initially be a serialized blob/text payload until a local vector extension is explicitly specified. Query evidence still resolves through `ideas`, not this table.

## Existing data mapping

There is no existing database or file-backed idea store to migrate. The current `.env.example` values configure the future runtime rather than represent persisted user data.

Initial runtime data maps into SQLite as follows:

| Existing or planned source | SQLite destination | Notes |
| --- | --- | --- |
| Manual `POST /v1/ideas` text, optional idempotency key, source ref, capture time, metadata | `raw_events`, `idea_drafts`, `ideas`, `idea_fts` | Store the request as a manual raw event first, derive one draft, persist one idea, then update FTS. |
| Generic webhook event | `raw_events`, zero or more `idea_drafts`, zero or more `ideas`, `idea_fts` | Connector validation decides whether the event yields ideas; raw event remains even when ignored. |
| Telegram/Discord/email provider message | `raw_events`, `idea_drafts`, `ideas`, `idea_fts` | Provider message IDs and source timestamps feed `provider_event_id`, `dedupe_key`, `occurred_at`, and `captured_at`. |
| Query/search evidence | `ideas`, `idea_fts`, later `embeddings` | Search indexes return ranked IDs/snippets; answers cite stored `ideas`. |
| Provider names, model names, base URLs, log level, database URL | Environment/config files read by `config.py` | Configuration stays outside SQLite for the first foundation. Store only durable idea data in SQLite. |
| API keys, bot tokens, email credentials, OAuth/proxy/local login material | Credential provider storage outside this schema | Secrets must not be migrated into SQLite by default. A future credential-provider spec may define encrypted/session storage separately. |

## Migration ordering

1. Create `schema_migrations` before applying numbered migration files, or bootstrap it as migration runner state.
2. Create `raw_events` first because ingestion must preserve source payloads before any derived records are created.
3. Create `idea_drafts` next with a foreign key to `raw_events` so extraction output can be stored and reprocessed.
4. Create `ideas` with foreign keys to `raw_events` and `idea_drafts` so canonical ideas keep citation lineage.
5. Create `idea_tags` after `ideas` because it is a derived filter projection.
6. Create `idea_fts` after `ideas` because it indexes canonical idea rows and can be rebuilt from storage.
7. Defer `embeddings` until after FTS-backed search and cited query tests pass; if created early, leave it unused behind `EmbeddingProvider` and `SearchIndex` contracts.

## Compatibility and migration assumptions

- SQLite is the first required backend; Postgres + pgvector remains optional until the SQLite path is healthy.
- Use text IDs and ISO-8601 UTC timestamps for portability across SQLite and future Postgres migrations.
- Store JSON payloads as text in SQLite with application-level validation so the schema remains easy to port.
- Enable foreign keys for SQLite connections before writes.
- Keep search/embedding tables as rebuildable projections; authoritative text, timestamps, metadata, and citation lineage remain in `raw_events`, `idea_drafts`, and `ideas`.
- The first migration does not import secrets from `.env`; credential persistence is a separate credential-provider concern.
- There is no legacy user data migration yet. The first migration only creates empty tables and indexes.
