from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_doc(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_sqlite_schema_plan_covers_initial_foundation_tables() -> None:
    plan = read_doc("docs/specs/sqlite-schema-plan.md")

    for table_name in [
        "schema_migrations",
        "raw_events",
        "idea_drafts",
        "ideas",
        "idea_tags",
        "idea_fts",
        "embeddings",
    ]:
        assert f"`{table_name}`" in plan

    assert "Primary key" in plan
    assert "Indexes" in plan
    assert "Timestamps" in plan


def test_sqlite_schema_plan_maps_existing_touchpoints_and_migration_order() -> None:
    plan = read_doc("docs/specs/sqlite-schema-plan.md")

    assert "## Current persistence and configuration touchpoints" in plan
    assert "## Existing data mapping" in plan
    assert "## Migration ordering" in plan
    assert "`IDEA_INBOX_DATABASE_URL`" in plan
    assert "`idea-inbox migrate`" in plan
    assert "Connector raw payloads" in plan
    assert "Configuration stays outside SQLite" in plan
    assert "Secrets must not be migrated into SQLite" in plan
