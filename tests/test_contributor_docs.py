from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_doc(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_quick_start_uses_current_smoke_command_not_planned_dev_command() -> None:
    readme = read_doc("README.md")

    assert "uv run idea-inbox\n" in readme
    assert "uv run idea-inbox dev" not in readme
    assert "only verifies that the package and CLI entry point run" in readme


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


def test_initial_product_spec_keeps_query_before_optional_hybrid_search() -> None:
    initial_spec = read_doc("docs/specs/initial-product-spec.md")

    assert initial_spec.index("5. Cited query endpoint.") < initial_spec.index(
        "6. Embeddings and hybrid search."
    )


def test_discovery_inventory_is_marked_as_resolved_by_mvp_spec() -> None:
    discovery = read_doc("docs/specs/mvp-discovery-inventory.md")

    assert "ADR-006-mvp-scope-and-local-first-self-hosting.md" in discovery
    assert "The open questions below were resolved by `mvp-architecture-spec.md`" in discovery
    assert "README quick start references `uv run idea-inbox dev`" not in discovery
    assert "ghcr.io/triskattie/idea-inbox:latest" not in discovery
