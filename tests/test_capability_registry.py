from idea_inbox.capabilities.registry import CapabilityRegistry, builtin_capabilities
from idea_inbox.core.capabilities import Capability, CapabilityKind, ConfigRequirement


def test_builtin_registry_reports_enabled_baseline_and_disabled_query_ai() -> None:
    registry = CapabilityRegistry()

    report = registry.validate()
    records = {record.name: record for record in report.capabilities}

    assert records["core"].origin == "built-in"
    assert records["core"].status == "enabled"
    assert records["manual-capture"].status == "enabled"
    assert records["sqlite-storage"].status == "enabled"
    assert records["sqlite-fts-search"].status == "enabled"
    assert records["query-ai"].status == "disabled"
    assert records["query-ai"].effective_enabled is False
    assert registry.is_enabled("sqlite-fts-search") is True
    assert registry.is_enabled("query-ai") is False


def test_enabled_capability_reports_missing_secret_configuration_without_value() -> None:
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
    )
    registry = CapabilityRegistry(
        builtin_capabilities(),
        installed_capabilities=(provider,),
        enabled_overrides={"openai-compatible-provider": True},
        config_values={"IDEA_INBOX_OPENAI_API_KEY": ""},
    )

    record = registry.get_capability("openai-compatible-provider")

    assert record is not None
    assert record.origin == "installed"
    assert record.effective_enabled is True
    assert record.status == "misconfigured"
    assert record.diagnostics == [
        {
            "code": "missing_configuration",
            "field": "IDEA_INBOX_OPENAI_API_KEY",
            "message": "Required secret IDEA_INBOX_OPENAI_API_KEY is missing.",
        }
    ]


def test_enabled_capability_reports_disabled_and_unavailable_dependencies() -> None:
    query = Capability(
        name="experimental-query",
        kind=CapabilityKind.QUERY,
        dependencies=("query-ai", "missing-provider"),
        default_enabled=False,
    )
    registry = CapabilityRegistry(
        builtin_capabilities(),
        installed_capabilities=(query,),
        enabled_overrides={"experimental-query": True},
    )

    record = registry.get_capability("experimental-query")
    missing = registry.get_capability("missing-provider")

    assert record is not None
    assert record.status == "misconfigured"
    assert {
        "code": "dependency_disabled",
        "field": "query-ai",
        "message": "Dependency query-ai is disabled.",
    } in record.diagnostics
    assert {
        "code": "dependency_unavailable",
        "field": "missing-provider",
        "message": "Dependency missing-provider is unavailable.",
    } in record.diagnostics
    assert missing is not None
    assert missing.origin == "unavailable"
    assert missing.status == "misconfigured"


def test_cycle_participants_are_reported_as_misconfigured() -> None:
    alpha = Capability(
        name="alpha-module",
        kind=CapabilityKind.CONNECTOR,
        dependencies=("beta-module",),
        default_enabled=True,
    )
    beta = Capability(
        name="beta-module",
        kind=CapabilityKind.CONNECTOR,
        dependencies=("alpha-module",),
        default_enabled=True,
    )
    registry = CapabilityRegistry(installed_capabilities=(alpha, beta))

    alpha_record = registry.get_capability("alpha-module")
    beta_record = registry.get_capability("beta-module")

    assert alpha_record is not None
    assert beta_record is not None
    assert alpha_record.status == "misconfigured"
    assert beta_record.status == "misconfigured"
    assert alpha_record.diagnostics == [
        {
            "code": "dependency_cycle",
            "field": "alpha-module",
            "message": "Capability dependency cycle includes alpha-module.",
        }
    ]
    assert beta_record.diagnostics == [
        {
            "code": "dependency_cycle",
            "field": "beta-module",
            "message": "Capability dependency cycle includes beta-module.",
        }
    ]
