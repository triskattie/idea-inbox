# Contributing

Idea Inbox is designed for small, safe contributions. The base app should stay lightweight; AI, embeddings, connectors, hosted providers, and heavier deployment profiles should be addable as opt-in modules, not rewrites or default requirements.

## Development workflow

Use the gated workflow:

```text
SPEC → PLAN → TASKS → TEST → IMPLEMENT → VERIFY → REVIEW → COMMIT
```

No feature work starts without:

- a written spec or accepted issue
- acceptance criteria
- a test plan
- clear out-of-scope boundaries

## Baseline verification commands

Install uv first if it is not already available: https://docs.astral.sh/uv/getting-started/installation/

Run these checks before handing off a change.

Runnable now:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Add feature code test-first: write the failing test before the implementation, then keep
the baseline verification commands green.

If uv is unavailable, use an isolated virtual environment instead of the system Python:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e . pytest ruff
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest
```

Planned until configured:

- Type checking with mypy. Do not require `mypy` in local verification or CI until it is
  added to the dev dependency group and configured in `pyproject.toml`.

## Architecture rules

Stable extension boundaries:

- `Connector` — Discord, Telegram, Email, WhatsApp, Webhook, CLI, etc.
- `ModelProvider` — chat/completion models.
- `EmbeddingProvider` — embedding models.
- `CredentialProvider` — API key, local, OAuth/device login, Codex-style login, proxy login.
- `SearchIndex` — FTS/vector/hybrid search backends.
- `StorageBackend` — SQLite, Postgres, etc.

Rules:

- New platforms/providers are modules, not rewrites.
- AI, embeddings, connector runtimes, hosted providers, and vector databases are opt-in capabilities, not base-app prerequisites.
- Core domain code must not import provider SDK types.
- Route handlers stay thin; domain logic lives in services/core modules.
- Dependency injection over global clients.
- No hidden network calls in constructors.
- No secrets in logs.

### Capability registry maintenance

Capabilities are SDK-free metadata records, not adapter implementations. Declare them with
`Capability` and `ConfigRequirement` from `idea_inbox.core.capabilities`, and register installed
metadata through `CapabilityRegistry(installed_capabilities=...)` in application-level code. Do not
add provider SDK imports, connector SDK imports, package discovery, network calls, migrations, or
client startup to `idea_inbox.core` or to registry validation.

Use stable lowercase kebab-case names because capability names are public API. Choose one of the
current kinds: `core`, `query`, `provider`, `connector`, `search`, or `storage`. Keep dependencies
as capability names, not Python packages or environment variables.

Default enabled state is policy, not proof of readiness: `effective_enabled` is operator override
if present, otherwise `default_enabled`. Base capabilities needed for the current local MVP may
default to enabled; AI query, model/embedding providers, external connectors, vector search, hosted
services, and heavier deployment profiles default to disabled until deliberately enabled.

Configuration requirements should name public config keys or credential handles. Set
`required_when_enabled=True` only when a missing value makes an enabled capability unusable, and
set `secret=True` for credentials. Registry diagnostics may report a secret key as missing, but
must never expose secret values.

When adding or changing capability metadata, update `docs/specs/capability-registry-spec.md`, add
or adjust tests in `tests/test_capability_registry.py`, and keep README terminology aligned with
the implemented `CapabilityRegistry` API and status meanings.

### SQLite FTS search maintenance

The current SQLite search index is `idea_fts`, a rebuildable FTS5 projection over canonical
`Idea.text`, normalized tags, and `Idea.source_ref`. Keep it synchronized by preserving the
`ideas_ai`, `ideas_au`, and `ideas_ad` triggers in `0002_idea_fts.sql` when changing idea
fields or write paths. If a new idea field should become searchable, update the migration or
add a new migration, update `SQLiteFTSSearchIndex.search()` only if ranking/filtering changes,
and add tests proving insert, update, delete, rebuild, and raw-payload non-indexing behavior.

Do not index `raw_events.payload` directly. Raw events are the authoritative audit trail;
search and cited answers must resolve through stored `ideas` and stable idea IDs.

### SQLite local development database

The default local database is `sqlite:///./data/idea-inbox.sqlite3`, configured through
`IDEA_INBOX_DATABASE_URL` in `.env.example`. Contributors may instead set
`IDEA_INBOX_SQLITE_PATH` to a plain file path, but should not set both variables at once.

Apply or refresh the local schema with:

```bash
uv run idea-inbox migrate
```

For a throwaway development reset, stop any running Idea Inbox process, remove the local SQLite
file, and re-run `uv run idea-inbox migrate`:

```bash
rm -f data/idea-inbox.sqlite3
uv run idea-inbox migrate
```

Only use this reset for disposable local development data. SQLite migrations preserve raw
events and derived ideas in normal use; deleting the database removes that audit trail.

## Testing standards

Strict TDD for behavior changes:

```text
RED: write failing test
GREEN: minimal code
REFACTOR: clean while green
```

Testing rules:

- No real Discord/Telegram/email calls in normal tests.
- Use fixtures for webhook/provider payloads.
- Mock model providers deterministically.
- Query tests must verify citations.
- Bug fixes require a failing regression test first.

## API standards

- Versioned REST endpoints under `/v1`.
- Keep the runtime dependency-free until a framework/schema dependency is explicitly accepted.
  Current stdlib WSGI handlers use dataclass request DTOs, typed response dictionaries, and
  manual validation at the HTTP boundary instead of external schema models.
- Consistent error shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request body",
    "details": {}
  }
}
```

- All list endpoints are paginated from day one.
- Public fields are additive; no breaking changes without deprecation.
- Third-party webhook payloads are untrusted and validated at the boundary.

## Documentation standards

Write ADRs for decisions that are expensive to reverse. Use docs for user-facing how-to material. Use types and tests for code-level contracts.

## Git standards

Use conventional commits:

```text
feat: add manual idea ingestion endpoint
fix: make raw event ingestion idempotent
test: add telegram payload normalization fixtures
docs: add connector authoring guide
refactor: extract search ranking service
chore: configure ruff and mypy
```

Each commit should do one logical thing, pass verification, and avoid unrelated formatting churn.

## Definition of done

A task is done only when:

- acceptance criteria are met
- tests are written and passing
- lint/format checks pass, and configured type checks pass
- docs are updated if behavior/user-facing/API changed
- ADR is added/updated if architecture changed
- Docker/dev setup still works if touched
- change summary identifies what was touched and what was intentionally not touched
