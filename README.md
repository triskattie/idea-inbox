# Idea Inbox

Self-hosted idea capture and retrieval assistant for collecting ideas from chat, email, webhooks, and other inboxes, then searching them locally and optionally querying them later with cited AI-assisted answers.

## Goals

- Easy self-hosting with a lightweight default path.
- Contributor-friendly architecture and documentation.
- Stable extension points for connectors, model providers, embedding providers, credential providers, storage, and search.
- Optional capability modules for AI query, embeddings, platform connectors, and heavier deployment profiles; the base app must not automatically opt users into AI or nonessential integrations.
- No lock-in to OpenAI API keys: local AI, OpenAI-compatible endpoints, OAuth/proxy/Codex-style flows should be addable without rewrites.

## Human-supervised Hermes Agent development

Idea Inbox is a human-directed, AI-assisted project: it has been mainly coded using Hermes Agent, with Tris acting as human supervisor, creative director, product owner, and reviewer.

See [Development with Hermes Agent](docs/development-with-hermes.md) for the collaboration model and the Hermes features used so far.

## Release scopes

### v0.1.0

The first release is a local manual capture and search MVP:

1. Manual API idea capture.
2. Raw event ingestion pipeline.
3. SQLite default storage and full-text search.
4. Runnable local `dev`/`serve` API startup.
5. Documentation for the current setup, usage, and limitations.

### v0.2.0 cited-query foundation

v0.2.0 adds the cited-query foundation without making AI a base requirement. The WSGI app
exposes `POST /v1/query`, but the built-in `query-ai` capability is `default_enabled=False`, so
normal `dev` and `serve` runs return a typed `503 CAPABILITY_DISABLED` response until an embedded
or test harness deliberately supplies an enabled capability registry. The implemented foundation
uses deterministic SQLite FTS retrieval plus a local/mock answerer; it does not require real model
credentials and does not make hosted-model calls.

This release is intentionally narrow: it is not general web search, connector ingestion,
embeddings, hybrid/vector search, a browser/mobile UI, production auth/multi-user ownership, or a
public internet service. Assume localhost or a private network such as Tailscale unless you add your
own access control. Phase 7 adds opt-in provider-adapter boundaries for mock, OpenAI-compatible,
and Ollama-style model providers, but no public CLI toggle or package discovery path enables them
in normal `dev`/`serve` runs yet. Telegram/email/Discord connectors, vector search, and optional
Postgres + pgvector deployment profiles remain later opt-in modules. See
[ADR-007](docs/decisions/ADR-007-optional-capability-modules.md).

## Development status

This repository now has a runnable local SQLite path, deterministic migrations, an importable
WSGI API for manual capture, FTS-backed search, and default-disabled cited query, plus `dev`/`serve`
commands that start the local API after applying pending migrations. Provider adapter boundaries are
implemented for explicit in-process harnesses, while external connectors, public provider
enablement, embeddings/hybrid search, UI, production auth, and packaged deployment assets are still
planned. See:

- [Development standards](CONTRIBUTING.md)
- [Architecture overview](docs/architecture.md)
- [ADRs](docs/decisions/)
- [Initial project spec](docs/specs/initial-product-spec.md)

## Quick start

Current local development setup:

```bash
uv sync
cp .env.example .env
uv run idea-inbox
```

The default command prints top-level CLI help and exits `0`; it only verifies that the package and
CLI entry point run. The local development path uses SQLite plus mock/local providers by default;
it does not require hosted-model credentials, hidden outbound model calls, or telemetry. Run
`uv run idea-inbox migrate` before using the importable WSGI API against a local database.

## SQLite setup

SQLite is the current runnable persistence path for local development and lightweight
self-hosting.

Defaults to `sqlite:///./data/idea-inbox.sqlite3` relative to the directory where the CLI is
run. The template `.env.example` sets the same value as `IDEA_INBOX_DATABASE_URL`.

Configure the database location with one of these settings:

- `IDEA_INBOX_DATABASE_URL` accepts `sqlite:///` and `sqlite+aiosqlite:///` URLs. Relative
  paths, such as `sqlite:///./data/idea-inbox.sqlite3`, resolve from the current project root.
- `IDEA_INBOX_SQLITE_PATH` accepts a plain SQLite file path, such as
  `./data/idea-inbox.sqlite3` or `/srv/idea-inbox/idea-inbox.sqlite3`.

Do not set `IDEA_INBOX_DATABASE_URL` and `IDEA_INBOX_SQLITE_PATH` together; startup and
migration commands reject conflicting database location settings.

Other keys in `.env.example` are reserved for planned providers, connectors, and an API access
token gate. The current runtime only loads `IDEA_INBOX_ENV`, `IDEA_INBOX_LOG_LEVEL`,
`IDEA_INBOX_DATABASE_URL`, and `IDEA_INBOX_SQLITE_PATH`; setting `IDEA_INBOX_API_KEY` does not
protect `POST /v1/ideas` yet. Keep `serve` bound to `127.0.0.1` or put your own reverse proxy,
network ACL, or access control in front of it before exposing the API.

Initialize or update the schema with:

```bash
uv run idea-inbox migrate
```

To migrate a specific local database file without changing `.env`, run:

```bash
uv run idea-inbox migrate --database ./path/to/ideas.sqlite3
```

Migrations create parent directories for file-backed databases, record applied migration
versions/checksums in `schema_migrations`, and are safe to re-run when migration files are
unchanged. The first migrations create authoritative `raw_events`, `idea_drafts`, `ideas`, and
`idea_tags` tables plus the rebuildable `idea_fts` FTS5 projection.

## Manual idea capture

The importable WSGI app accepts manual ideas as:

```text
POST /v1/ideas
```

The JSON request body must be an object with non-empty string `text`. Optional fields are
`idempotency_key`, `source_ref`, `actor_ref`, `captured_at`, `metadata`, and `tags`. Text,
idempotency keys, and string references are trimmed; blank tags are ignored; tags are lower-cased
and de-duplicated; metadata must be a JSON object. Validation failures return the standard
`400 VALIDATION_ERROR` response with the actionable field in `error.details.field`.

Field limits in the MVP are: `text` up to 10,000 characters, `idempotency_key`, `source_ref`, and
`actor_ref` up to 512 characters each, at most 50 tags, and each tag up to 64 characters after
trimming. `tags` must be a JSON list of strings. `captured_at` is currently accepted as a trimmed
string and used as the idea capture time when present; strict ISO-8601 parsing is not enforced yet.

Successful manual capture stores the normalized request as a `manual` raw event first, then
persists one idea draft and one canonical idea for search/citation lineage. The public response
returns the created idea id, normalized text, source metadata, capture timestamp, metadata, and
tags without exposing persistence internals.

Manual capture is idempotent by source-scoped dedupe key. If `idempotency_key` is supplied,
replays with the same key return the originally stored idea without creating another raw event,
draft, or idea. If no key is supplied, Idea Inbox derives the dedupe key from the normalized
request body so exact request replays are also idempotent.

Known MVP limitations: manual capture has no dedicated auth/access-token gate yet, and there is no
direct `idea-inbox capture` CLI wrapper; use the `/v1` HTTP API through `dev` or `serve`.

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

## Cited query foundation

The WSGI app exposes cited query as:

```text
POST /v1/query
```

`query-ai` is disabled by default. In a normal local `dev` or `serve` run, this request returns
`503 Service Unavailable` with the standard error envelope and does not validate the body, run
retrieval, initialize providers, or make network calls:

```json
{
  "error": {
    "code": "CAPABILITY_DISABLED",
    "message": "Cited query is not enabled for this Idea Inbox instance.",
    "details": {
      "capability": "query-ai",
      "status": "disabled",
      "reason": "Enable and configure the query-ai capability before using POST /v1/query."
    }
  }
}
```

The current release has no public CLI or `.env` switch that enables query for `idea-inbox dev` or
`idea-inbox serve`. Setting `IDEA_INBOX_CHAT_PROVIDER=mock` alone is only reserved configuration;
it does not enable query in the packaged server path. Tests and embedded local harnesses can enable
the foundation by constructing `create_app(...)` with a `CapabilityRegistry` that supplies:

- an installed deterministic `model-provider` capability,
- `enabled_overrides={"query-ai": True}`, and
- `config_values={"IDEA_INBOX_CHAT_PROVIDER": "mock"}`.

To disable it again, remove the override, set `enabled_overrides={"query-ai": False}`, or use the
default `CapabilityRegistry()`.

When enabled this foundation validates `{ "query": "...", "limit": 10, "filters": {"source":
"manual"}, "include_hits": true }`, retrieves stored ideas through SQLite FTS, resolves each hit
through authoritative storage, and returns either:

- `answer.grounding == "stored_ideas"` with non-empty citations pointing to persisted ideas, safe
  source metadata, and provenance IDs when available, or
- `answer.grounding == "no_relevant_stored_ideas"` with empty `citations` and `hits`.

It is not general web search and it cannot answer from uncaptured connector data, embeddings, model
world knowledge, or raw event payload bodies. See
[the cited-query API contract](docs/specs/cited-query-api-contract.md) for the full request,
response, citation, and fabrication rules.

## Optional module roadmap

The default install should continue to support manual capture and SQLite keyword search without
AI, hosted model credentials, connector tokens, vector databases, or hidden outbound calls. The
explicit module plan is:

1. Define a lightweight capability/module contract and registry before adding features that would
   otherwise make AI or heavyweight integrations feel mandatory.
2. Put cited natural-language query behind an explicit `query-ai` capability/module. The
   v0.2.0 foundation contract for `POST /v1/query` is documented in
   [cited-query-api-contract.md](docs/specs/cited-query-api-contract.md): grounded answers must
   cite persisted ideas, no-evidence responses must return empty citations with an explicit
   `no_relevant_stored_ideas` grounding value, and disabled query capability returns
   `CAPABILITY_DISABLED` without provider calls. Tests may use deterministic local/mock providers,
   but real model calls must require deliberate configuration.
3. Add embeddings/hybrid search, platform connectors, hosted/local model providers, and
   Postgres/pgvector deployment profiles as separately installable or enableable modules.
4. Keep core startup, migration, capture, and FTS search healthy when no optional modules are
   installed.

## Capability registry

The Phase 5 capability registry makes the module boundary explicit without adding AI query,
embeddings, connector runtimes, provider SDKs, package discovery, or heavier integrations. This
phase only makes capabilities explicit so later optional modules can be validated before startup;
manual capture, SQLite storage, and FTS-backed keyword search remain the default runnable path.

Capability metadata lives in SDK-free dataclasses under `idea_inbox.core.capabilities` and is
validated by `CapabilityRegistry` in `idea_inbox.capabilities.registry`. Public capability names
are stable lowercase kebab-case slugs. Current metadata fields are:

| Field | Meaning |
| --- | --- |
| `name` | Stable public slug such as `core`, `sqlite-storage`, `manual-capture`, `sqlite-fts-search`, or `query-ai`. |
| `kind` | Category: `core`, `query`, `provider`, `connector`, `search`, or `storage`. |
| `dependencies` | Other capability names that must be present and enabled before this capability can be enabled. |
| `default_enabled` | Built-in policy when no operator override exists. Base capabilities default to `true`; AI/provider/connector-style capabilities default to `false`. |
| `configuration` | `ConfigRequirement` records describing config keys or credential handles. Missing required values are checked only when the capability is effectively enabled. |
| `description` | One-sentence display text. |
| `version` | Optional module or contract version. |
| `owner` | `builtin` for base package metadata or the installed module/package identifier. |

Registry records expose origin separately from readiness. `built-in` means metadata ships with the
base package, `installed` means metadata came from an explicitly supplied module, and
`unavailable` means a referenced capability has no metadata. Status values are `enabled`,
`disabled`, and `misconfigured`: enabled means present, effectively enabled, dependencies are
enabled, and required configuration is present; disabled means present but inactive; misconfigured
means enabled policy found missing/disabled/unavailable/misconfigured dependencies, a dependency
cycle, or missing required configuration. `effective_enabled` is computed as operator override if
present, otherwise `default_enabled`.

The API is side-effect-light and does not initialize adapters or make network calls:

- `list_capabilities()` returns all known records with origin, effective state, status, and diagnostics.
- `get_capability(name)` returns one record or `None`.
- `is_enabled(name)` is `true` only for present, enabled, valid capabilities.
- `validate()` returns a full report with flattened diagnostics available on the report.

Example installed capability declaration:

```python
from idea_inbox.capabilities.registry import CapabilityRegistry
from idea_inbox.core.capabilities import Capability, CapabilityKind, ConfigRequirement

provider = Capability(
    name="openai-compatible-provider",
    kind=CapabilityKind.PROVIDER,
    dependencies=("core",),
    default_enabled=False,
    configuration=(
        ConfigRequirement(
            key="IDEA_INBOX_OPENAI_API_KEY",
            required_when_enabled=True,
            secret=True,
            description="OpenAI-compatible credential handle.",
        ),
    ),
    description="Planned OpenAI-compatible model provider.",
    owner="example-provider-package",
)

registry = CapabilityRegistry(installed_capabilities=(provider,))
record = registry.get_capability("openai-compatible-provider")
```

## CLI usage

### Smoke command

```bash
uv run idea-inbox
```

Run this from the repository root after `uv sync`. It prints top-level CLI help and exits `0`.
It does not start an API server, create or migrate a database, call model providers, open
network listeners, or emit telemetry.

To try the current manual capture flow locally, start the API against a disposable SQLite file:

```bash
uv run idea-inbox serve --host 127.0.0.1 --port 8080 --database ./data/idea-inbox.sqlite3
```

Then submit a manual idea from another terminal:

```bash
curl -i -X POST http://127.0.0.1:8080/v1/ideas \
  -H 'Content-Type: application/json' \
  -d '{"text":"Prototype local-first capture before connector work.","source_ref":"note-1","actor_ref":"local-operator","tags":["Capture","local-ai"],"metadata":{"surface":"curl"}}'
```

The server responds `201 Created` with an `item` containing the generated `idea_id`, normalized
text, `source: "manual"`, optional source metadata, capture timestamp, metadata, and normalized
tags. The submitted payload is saved as a `manual` raw event before the derived draft and
canonical idea are persisted.

### Startup commands

The CLI can migrate SQLite storage and start the WSGI `/v1` API used for manual capture and
search. Long-running server commands validate configuration, apply pending SQLite migrations,
print the local API URL, and then serve requests until stopped by the operator.

| Command | Purpose | Current behavior |
| --- | --- | --- |
| `uv run idea-inbox dev [--host 127.0.0.1] [--port 8080] [--database ./data/idea-inbox.sqlite3]` | Start the local development API using SQLite and mock/local providers by default. | Applies SQLite migrations, serves `/v1/ideas`, `/v1/ideas/search`, and default-disabled `/v1/query`, and exits when stopped. |
| `uv run idea-inbox migrate [--database ./data/idea-inbox.sqlite3]` | Apply deterministic SQLite storage migrations, including the FTS5 projection. | Applies migrations and exits `0`; exits `1` with an actionable error if configuration is invalid, SQLite FTS5 is unavailable, or a migration fails. |
| `uv run idea-inbox serve [--host 127.0.0.1] [--port 8080] [--database ./data/idea-inbox.sqlite3]` | Start the configured `/v1` API for local or self-hosted use. | Applies SQLite migrations, serves `/v1/ideas`, `/v1/ideas/search`, and default-disabled `/v1/query`, and exits when stopped. |

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
- `Address already in use` from `dev` or `serve` means another process is already bound to the
  requested host/port; choose another `--port` or stop the existing process.

Planned self-hosting targets are documented in [Self-hosting](docs/self-hosting.md). Docker
and Docker Compose support are planned deployment targets, but this repository does not yet
include a Dockerfile, Compose file, or confirmed published image.
