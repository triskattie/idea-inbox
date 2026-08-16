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


def test_installed_capability_defaulting_disabled_stays_inert() -> None:
    provider = Capability(
        name="hosted-model-provider",
        kind=CapabilityKind.PROVIDER,
        dependencies=("core",),
        default_enabled=False,
        configuration=(
            ConfigRequirement(
                key="IDEA_INBOX_HOSTED_MODEL_TOKEN",
                required_when_enabled=True,
                secret=True,
                description="Hosted model credential handle.",
            ),
        ),
    )
    registry = CapabilityRegistry(installed_capabilities=(provider,), config_values={})

    record = registry.get_capability("hosted-model-provider")

    assert record is not None
    assert record.origin == "installed"
    assert record.default_enabled is False
    assert record.effective_enabled is False
    assert record.status == "disabled"
    assert record.diagnostics == []
    assert registry.is_enabled("hosted-model-provider") is False


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


def test_valid_installed_capability_with_enabled_dependencies_reports_enabled() -> None:
    provider = Capability(
        name="local-model-provider",
        kind=CapabilityKind.PROVIDER,
        dependencies=("core",),
        default_enabled=True,
        configuration=(
            ConfigRequirement(
                key="IDEA_INBOX_LOCAL_MODEL_URL",
                required_when_enabled=True,
                secret=False,
                description="Local model API endpoint.",
            ),
        ),
    )
    query = Capability(
        name="local-ai-query",
        kind=CapabilityKind.QUERY,
        dependencies=("sqlite-fts-search", "local-model-provider"),
        default_enabled=True,
    )
    registry = CapabilityRegistry(
        installed_capabilities=(provider, query),
        config_values={"IDEA_INBOX_LOCAL_MODEL_URL": "http://127.0.0.1:11434"},
    )

    provider_record = registry.get_capability("local-model-provider")
    query_record = registry.get_capability("local-ai-query")

    assert provider_record is not None
    assert query_record is not None
    assert provider_record.origin == "installed"
    assert provider_record.status == "enabled"
    assert provider_record.diagnostics == []
    assert query_record.origin == "installed"
    assert query_record.status == "enabled"
    assert query_record.effective_enabled is True
    assert query_record.diagnostics == []
    assert registry.is_enabled("local-ai-query") is True
