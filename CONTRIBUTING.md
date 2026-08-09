# Contributing

Idea Inbox is designed for small, safe contributions. New platforms and AI providers should be addable as modules, not rewrites.

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
- Core domain code must not import provider SDK types.
- Route handlers stay thin; domain logic lives in services/core modules.
- Dependency injection over global clients.
- No hidden network calls in constructors.
- No secrets in logs.

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
- Pydantic request/response schemas.
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
