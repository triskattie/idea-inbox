from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_doc(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def squash_whitespace(text: str) -> str:
    return " ".join(text.split())


def test_readme_quick_start_uses_current_smoke_command_not_planned_dev_command() -> None:
    readme = read_doc("README.md")
    quick_start = readme.split("## Quick start", 1)[1].split("## CLI usage", 1)[0]

    assert "uv run idea-inbox\n" in quick_start
    assert "uv run idea-inbox dev" not in quick_start
    assert "only verifies that the package and CLI entry point run" in squash_whitespace(
        quick_start
    )


def test_contributing_separates_runnable_commands_from_planned_type_checking() -> None:
    contributing = read_doc("CONTRIBUTING.md")

    assert "Runnable now:" in contributing
    assert "Planned until configured:" in contributing
    assert "uv run mypy src" not in contributing
    assert "Type checking with mypy" in contributing


def test_contributing_documents_uv_prerequisite_and_venv_fallback() -> None:
    contributing = read_doc("CONTRIBUTING.md")

    assert "Install uv first" in contributing
    assert "python3 -m venv .venv" in contributing
    assert ".venv/bin/python -m pytest" in contributing
    assert ".venv/bin/python -m ruff check ." in contributing


def test_initial_product_spec_plans_module_contract_before_optional_ai_query() -> None:
    initial_spec = read_doc("docs/specs/initial-product-spec.md")

    assert initial_spec.index(
        "5. Capability/module contract and registry plan."
    ) < initial_spec.index("6. Optional cited query capability/module.")
    assert initial_spec.index("6. Optional cited query capability/module.") < initial_spec.index(
        "7. Optional embeddings and hybrid search module."
    )


def test_discovery_inventory_is_marked_as_resolved_by_mvp_spec() -> None:
    discovery = read_doc("docs/specs/mvp-discovery-inventory.md")

    assert "ADR-006-mvp-scope-and-local-first-self-hosting.md" in discovery
    assert "The open questions below were resolved by `mvp-architecture-spec.md`" in discovery
    assert "README quick start references `uv run idea-inbox dev`" not in discovery
    assert "ghcr.io/triskattie/idea-inbox:latest" not in discovery


def test_mvp_architecture_spec_defines_planned_cli_contract() -> None:
    mvp_spec = read_doc("docs/specs/mvp-architecture-spec.md")

    assert "### Planned CLI command contract" in mvp_spec
    assert "`idea-inbox dev`" in mvp_spec
    assert "`idea-inbox migrate`" in mvp_spec
    assert "`idea-inbox serve --host 127.0.0.1 --port 8080`" in mvp_spec
    assert "Unknown commands or invalid options" in mvp_spec
    assert (
        "Direct `idea-inbox capture`, `idea-inbox search`, "
        "or `idea-inbox query` commands are deferred" in mvp_spec
    )


def test_readme_documents_current_and_planned_cli_usage() -> None:
    readme = read_doc("README.md")

    assert "## CLI usage" in readme
    assert "### Smoke command" in readme
    assert "uv run idea-inbox\n" in readme
    assert "prints top-level CLI help and exits `0`" in readme
    assert "### Startup commands" in readme
    assert "start the WSGI `/v1` API" in readme
    assert (
        "`uv run idea-inbox dev [--host 127.0.0.1] [--port 8080] "
        "[--database ./data/idea-inbox.sqlite3]`" in readme
    )
    assert "`uv run idea-inbox migrate [--database ./data/idea-inbox.sqlite3]`" in readme
    assert (
        "`uv run idea-inbox serve [--host 127.0.0.1] [--port 8080] "
        "[--database ./data/idea-inbox.sqlite3]`" in readme
    )
    assert "Unknown commands or invalid options" in readme
    assert "Deferred direct content commands" in readme


def test_docs_describe_implemented_fts_search_behavior() -> None:
    readme = read_doc("README.md")
    architecture = read_doc("docs/architecture.md")
    self_hosting = read_doc("docs/self-hosting.md")
    sqlite_plan = read_doc("docs/specs/sqlite-schema-plan.md")
    mvp_spec = read_doc("docs/specs/mvp-architecture-spec.md")
    contributing = read_doc("CONTRIBUTING.md")

    assert "## FTS-backed search" in readme
    assert (
        "Searchable fields are canonical `Idea.text`, normalized idea tags, and `Idea.source_ref`"
        in readme
    )
    assert "Raw event payloads are deliberately not indexed or returned" in readme
    assert "SQLite FTS operators such as `OR`, prefix `*`, column filters, and `NEAR`" in readme
    assert "`limit` defaults to `10`" in readme

    assert "## Current search projection" in architecture
    assert "`idea_fts` virtual table over canonical idea text" in architecture
    assert "Raw event payloads are preserved for audit" in architecture

    assert "## Current SQLite migrations and search index" in self_hosting
    assert "The Python `sqlite3` build must include SQLite FTS5" in self_hosting
    assert "SQLiteFTSSearchIndex(storage).rebuild()" in self_hosting

    assert "## Implemented FTS search behavior" in sqlite_plan
    assert "`bm25(idea_fts)`" in sqlite_plan
    assert "Raw SQLite FTS syntax is not exposed" in sqlite_plan

    assert "Implemented behavior as of the FTS search slice" in mvp_spec
    assert "Searchable fields are `Idea.text`, normalized tags, and `Idea.source_ref`" in mvp_spec
    assert "`next_cursor` is currently always `null`" in mvp_spec

    assert "### SQLite FTS search maintenance" in contributing
    assert "preserving the\n`ideas_ai`, `ideas_au`, and `ideas_ad` triggers" in contributing


def test_docs_describe_sqlite_setup_and_migration_behavior() -> None:
    readme = read_doc("README.md")
    contributing = read_doc("CONTRIBUTING.md")
    self_hosting = read_doc("docs/self-hosting.md")
    env_example = read_doc(".env.example")

    assert "IDEA_INBOX_DATABASE_URL=sqlite:///./data/idea-inbox.sqlite3" in env_example
    assert (
        "Alternative: set IDEA_INBOX_SQLITE_PATH instead of IDEA_INBOX_DATABASE_URL" in env_example
    )

    assert "## SQLite setup" in readme
    assert "uv run idea-inbox migrate" in readme
    assert "Defaults to `sqlite:///./data/idea-inbox.sqlite3`" in readme
    assert (
        "`IDEA_INBOX_DATABASE_URL` accepts `sqlite:///` and `sqlite+aiosqlite:///` URLs" in readme
    )
    assert "Do not set `IDEA_INBOX_DATABASE_URL` and `IDEA_INBOX_SQLITE_PATH` together" in readme

    assert "### SQLite local development database" in contributing
    assert "rm -f data/idea-inbox.sqlite3" in contributing
    assert "re-run `uv run idea-inbox migrate`" in contributing

    assert "## SQLite configuration" in self_hosting
    assert "`uv run idea-inbox migrate --database ./path/to/ideas.sqlite3`" in self_hosting
    assert "Migration checksums are recorded in `schema_migrations`" in self_hosting
    assert "delete the\nconfigured `.sqlite3` file and run migrations again" in self_hosting


def test_docs_track_current_cli_api_and_manual_capture_surface() -> None:
    readme = read_doc("README.md")
    self_hosting = read_doc("docs/self-hosting.md")
    connectors = read_doc("docs/connectors.md")
    contributing = read_doc("CONTRIBUTING.md")
    changelog = read_doc("CHANGELOG.md")

    assert "Address already in use` from `dev` or `serve`" in readme
    assert "not-implemented message from `dev`, `migrate`, or `serve`" not in readme
    assert "not-implemented message from `dev` or `serve`" not in readme

    assert "## Current local development path" in self_hosting
    assert "placeholder CLI" not in self_hosting
    assert "smoke-only" not in self_hosting
    assert "POST /v1/ideas" in self_hosting
    assert "GET /v1/ideas/search?q=...&limit=10" in self_hosting
    assert "uv run idea-inbox dev --host 127.0.0.1 --port 8080" in self_hosting
    assert "do not start a\nlong-running HTTP process" not in self_hosting

    assert "## Implemented connectors" in connectors
    assert "- Manual API (`POST /v1/ideas`)" in connectors
    assert "- Manual API" not in connectors.split("## Planned connectors", 1)[1]

    assert "Pydantic request/response schemas" not in contributing
    assert "dataclass request DTOs" in contributing
    assert "manual validation" in contributing

    assert "runnable `dev`/`serve` WSGI API startup" in changelog
    assert "Manual idea capture through `POST /v1/ideas`" in changelog
    assert "WSGI API endpoints for manual capture and FTS-backed idea search" in changelog


def test_project_documents_human_supervised_hermes_development() -> None:
    readme = read_doc("README.md")
    doc = read_doc("docs/development-with-hermes.md")

    assert "Human-supervised Hermes Agent development" in readme
    assert "docs/development-with-hermes.md" in readme
    assert "mainly coded using Hermes Agent" in doc
    assert "human supervisor" in doc
    assert "creative director" in doc
    assert "planning" in doc
    assert "skills" in doc
    assert "tool-based verification" in doc


def test_docs_define_optional_module_direction_before_ai_query() -> None:
    readme = read_doc("README.md")
    architecture = read_doc("docs/architecture.md")
    mvp_spec = read_doc("docs/specs/mvp-architecture-spec.md")
    adr = read_doc("docs/decisions/ADR-007-optional-capability-modules.md")
    capability_spec = read_doc("docs/specs/capability-registry-spec.md")
    contributing = read_doc("CONTRIBUTING.md")

    assert "## Optional module roadmap" in readme
    assert (
        "Put cited natural-language query behind an explicit `query-ai` capability/module" in readme
    )
    assert "AI-assisted query is an optional capability module" in architecture
    assert "## Explicit module plan" in mvp_spec
    assert "### Phase 5: Capability/module contract and registry" in mvp_spec
    assert "### Phase 6: Optional cited query capability" in mvp_spec
    assert mvp_spec.index("### Phase 5: Capability/module contract and registry") < mvp_spec.index(
        "### Phase 6: Optional cited query capability"
    )
    assert "ADR-007-optional-capability-modules.md" in mvp_spec
    assert "capability-registry-spec.md" in mvp_spec
    assert "AI is not a prerequisite for installation, startup, tests, or basic self-hosting" in adr
    assert "opt-in capabilities, not base-app prerequisites" in contributing

    assert "## Capability metadata shape" in capability_spec
    assert "## Lifecycle and status vocabulary" in capability_spec
    assert "## Registry API contract" in capability_spec
    assert "## Example capability record" in capability_spec
    assert "`query-ai`" in capability_spec
    assert "built-in" in capability_spec
    assert "installed" in capability_spec
    assert "enabled" in capability_spec
    assert "disabled" in capability_spec
    assert "unavailable" in capability_spec
    assert "misconfigured" in capability_spec
    assert "No AI query endpoint, model calls, embeddings" in capability_spec


def test_docs_describe_implemented_capability_registry_contract() -> None:
    readme = read_doc("README.md")
    contributing = read_doc("CONTRIBUTING.md")
    capability_spec = read_doc("docs/specs/capability-registry-spec.md")
    squashed_readme = squash_whitespace(readme)
    squashed_contributing = squash_whitespace(contributing)

    assert "## Capability registry" in readme
    assert "`CapabilityRegistry`" in readme
    assert "`list_capabilities()`" in readme
    assert "`effective_enabled`" in readme
    assert "operator override if present, otherwise `default_enabled`" in squashed_readme
    assert "This phase only makes capabilities explicit" in squashed_readme

    assert "### Capability registry maintenance" in contributing
    assert "lowercase kebab-case" in contributing
    assert "`ConfigRequirement`" in contributing
    assert "Do not add provider SDK imports" in squashed_contributing

    assert "Implemented in Phase 5" in capability_spec
    assert "`src/idea_inbox/capabilities/registry.py`" in capability_spec
    assert "CapabilityRegistry(installed_capabilities=(provider,))" in capability_spec
