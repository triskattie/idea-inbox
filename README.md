# Idea Inbox

Self-hosted idea capture and retrieval assistant for collecting ideas from chat, email, webhooks, and other inboxes, then querying them later with cited answers.

## Goals

- Easy self-hosting with a lightweight default path.
- Contributor-friendly architecture and documentation.
- Stable extension points for connectors, model providers, embedding providers, credential providers, storage, and search.
- No lock-in to OpenAI API keys: local AI, OpenAI-compatible endpoints, OAuth/proxy/Codex-style flows should be addable without rewrites.

## Human-supervised Hermes Agent development

Idea Inbox is a human-directed, AI-assisted project: it has been mainly coded using Hermes Agent, with Tris acting as human supervisor, creative director, product owner, and reviewer.

See [Development with Hermes Agent](docs/development-with-hermes.md) for the collaboration model and the Hermes features used so far.

## Planned MVP

1. Manual API idea capture.
2. Raw event ingestion pipeline.
3. SQLite default storage and full-text search.
4. Provider interfaces for embeddings and answer generation.
5. Cited query endpoint.
6. Telegram, email, and Discord connectors.
7. Optional Postgres + pgvector production profile.

## Development status

This repository is currently being initialized. See:

- [Development standards](CONTRIBUTING.md)
- [Architecture overview](docs/architecture.md)
- [ADRs](docs/decisions/)
- [Initial project spec](docs/specs/initial-product-spec.md)

## Quick start

Current local smoke setup:

```bash
uv sync
cp .env.example .env
uv run idea-inbox
```

This repository is still being initialized, so the current command only verifies that the package and CLI entry point run. The local development path uses SQLite plus mock/local
providers by default; it does not require hosted-model credentials, hidden outbound model
calls, or telemetry.

SQLite configuration now defaults to `sqlite:///./data/idea-inbox.sqlite3` relative to the
project root. Override the database location with `IDEA_INBOX_DATABASE_URL` or
`IDEA_INBOX_SQLITE_PATH`, but not both.

## FTS-backed search

The first search slice is available through the importable WSGI app as:

```text
GET /v1/ideas/search?q=local%20AI&limit=10
```

Search runs against the configured SQLite database after migrations have created the
`idea_fts` FTS5 projection. The current response shape is:

```json
{
  "items": [
    {
      "idea_id": "idea_...",
      "snippet": "<mark>local</mark> AI idea",
      "score": -1.23,
      "source": "manual",
      "captured_at": "2026-08-09T00:00:00Z"
    }
  ],
  "page": { "limit": 10, "next_cursor": null }
}
```

Searchable fields are canonical `Idea.text`, normalized idea tags, and `Idea.source_ref`.
Raw event payloads are deliberately not indexed or returned. Queries are tokenized into
Unicode word tokens, punctuation is ignored, and each token is quoted before it is passed to
SQLite FTS. This makes simple keyword searches safe and deterministic, but it also means raw
SQLite FTS operators such as `OR`, prefix `*`, column filters, and `NEAR` are not exposed yet.
Blank or punctuation-only `q` values return `400 VALIDATION_ERROR`. `limit` defaults to `10`
and must be between `1` and `50`.

Results are ordered by SQLite `bm25(idea_fts)` score, then newest `captured_at`, then stable
idea id. Snippets highlight matches from idea text with `<mark>...</mark>`. The endpoint does
not expose raw idea text or raw payload bodies in the response.

## CLI usage

### Smoke command

```bash
uv run idea-inbox
```

Run this from the repository root after `uv sync`. It prints top-level CLI help and exits `0`.
It does not start an API server, create or migrate a database, call model providers, open
network listeners, or emit telemetry.

### Startup commands

The CLI now parses the planned startup commands, but the API, storage migration, and server
runtime modules are still pending. Until those modules exist, startup commands validate their
arguments and then fail with actionable not-implemented messages.

| Command | Purpose | Current behavior |
| --- | --- | --- |
| `uv run idea-inbox dev [--host 127.0.0.1] [--port 8080]` | Start the local development API using SQLite and mock/local providers by default. | Parses options, then exits `1` because API startup is not implemented yet. |
| `uv run idea-inbox migrate [--database ./data/idea-inbox.sqlite3]` | Apply deterministic SQLite storage migrations, including the FTS5 projection. | Applies migrations and exits `0`; exits `1` with an actionable error if configuration is invalid, SQLite FTS5 is unavailable, or a migration fails. |
| `uv run idea-inbox serve [--host 127.0.0.1] [--port 8080]` | Start the configured `/v1` API for local or self-hosted use. | Parses options, then exits `1` because API server startup is not implemented yet. |

Help and validation:

```bash
uv run idea-inbox --help
uv run idea-inbox dev --help
uv run idea-inbox migrate --help
uv run idea-inbox serve --help
```

Help commands exit `0`. Unknown commands or invalid options, such as an invalid `--port`, print
usage plus an error and exit `2`.

Deferred direct content commands: `idea-inbox capture`, `idea-inbox search`, and
`idea-inbox query` are intentionally not part of the first CLI surface. The planned MVP exposes
capture, search, and cited query behavior through `/v1` HTTP API endpoints first.

Troubleshooting:

- `uv: command not found`: install uv from the official installer, or use the virtualenv
  fallback in [Contributing](CONTRIBUTING.md).
- A not-implemented message from `dev`, `migrate`, or `serve` means the parser accepted the
  command but the underlying runtime module is not built yet.

Planned self-hosting targets are documented in [Self-hosting](docs/self-hosting.md). Docker
and Docker Compose support are planned deployment targets, but this repository does not yet
include a Dockerfile, Compose file, or confirmed published image.
