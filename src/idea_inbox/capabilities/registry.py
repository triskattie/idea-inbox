"""Capability registry validation orchestration."""

import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace

from idea_inbox.config import DATABASE_URL_ENV, SQLITE_PATH_ENV, ConfigError, load_config
from idea_inbox.core.capabilities import (
    Capability,
    CapabilityKind,
    CapabilityOrigin,
    CapabilityRecord,
    CapabilityRegistryReport,
    CapabilityStatus,
    CapabilityValidationError,
    ConfigRequirement,
)

CapabilityMap = dict[str, tuple[Capability, CapabilityOrigin]]

QUERY_PROVIDER_SELECTIONS = {
    "mock": "mock-model-provider",
    "openai-compatible": "openai-compatible-model-provider",
    "ollama": "ollama-model-provider",
}


def builtin_capabilities() -> tuple[Capability, ...]:
    """Return built-in capability metadata shipped with the base package."""
    return (
        Capability(
            name="core",
            kind=CapabilityKind.CORE,
            default_enabled=True,
            description="Base domain models, configuration loading, and CLI skeleton.",
        ),
        Capability(
            name="sqlite-storage",
            kind=CapabilityKind.STORAGE,
            dependencies=("core",),
            default_enabled=True,
            configuration=(
                ConfigRequirement(
                    key=DATABASE_URL_ENV,
                    required_when_enabled=False,
                    secret=False,
                    description="SQLite database URL used by the default storage backend.",
                ),
                ConfigRequirement(
                    key=SQLITE_PATH_ENV,
                    required_when_enabled=False,
                    secret=False,
                    description="Alternative SQLite database path for local development.",
                ),
            ),
            description="Default SQLite persistence path.",
        ),
        Capability(
            name="manual-capture",
            kind=CapabilityKind.CONNECTOR,
            dependencies=("core", "sqlite-storage"),
            default_enabled=True,
            description="Manual idea capture through the local API.",
        ),
        Capability(
            name="sqlite-fts-search",
            kind=CapabilityKind.SEARCH,
            dependencies=("sqlite-storage",),
            default_enabled=True,
            description="SQLite FTS5 keyword search projection.",
        ),
        Capability(
            name="query-ai",
            kind=CapabilityKind.QUERY,
            dependencies=("sqlite-fts-search", "model-provider"),
            default_enabled=False,
            configuration=(
                ConfigRequirement(
                    key="IDEA_INBOX_CHAT_PROVIDER",
                    required_when_enabled=True,
                    secret=False,
                    description="Selects the enabled chat/model provider capability.",
                ),
            ),
            description="Planned cited natural-language query capability.",
        ),
    )


class CapabilityRegistry:
    """Validate capability metadata and report readiness without initializing adapters."""

    def __init__(
        self,
        built_in_capabilities: Iterable[Capability] | None = None,
        *,
        installed_capabilities: Iterable[Capability] = (),
        enabled_overrides: Mapping[str, bool] | None = None,
        config_values: Mapping[str, str] | None = None,
    ) -> None:
        built_ins = (
            builtin_capabilities() if built_in_capabilities is None else built_in_capabilities
        )
        self._capabilities = _capability_map(built_ins, installed_capabilities)
        self._enabled_overrides = dict(enabled_overrides or {})
        self._config_values = os.environ if config_values is None else config_values
        self._last_report: CapabilityRegistryReport | None = None

    def list_capabilities(self) -> list[CapabilityRecord]:
        """List all known capability records with current validation status."""
        return self.validate().capabilities

    def get_capability(self, name: str) -> CapabilityRecord | None:
        """Return one capability record by stable name when known or referenced."""
        return next(
            (record for record in self.validate().capabilities if record.name == name), None
        )

    def is_enabled(self, name: str) -> bool:
        """Return true only when a capability is present, enabled, and valid."""
        record = self.get_capability(name)
        return record is not None and record.status == CapabilityStatus.ENABLED

    def validate(self) -> CapabilityRegistryReport:
        """Return a complete side-effect-light capability validation report."""
        records: dict[str, CapabilityRecord] = {}
        cycle_members = _cycle_members(self._capabilities)
        names = set(self._capabilities) | set(self._enabled_overrides)

        def evaluate(name: str) -> CapabilityRecord:
            if name in records:
                return records[name]

            capability_with_origin = self._capabilities.get(name)
            if capability_with_origin is None:
                record = CapabilityRecord(
                    name=name,
                    kind=None,
                    origin=CapabilityOrigin.UNAVAILABLE,
                    default_enabled=False,
                    effective_enabled=False,
                    dependencies=(),
                    configuration=(),
                    status=CapabilityStatus.MISCONFIGURED,
                    diagnostics=[
                        {
                            "code": "capability_unavailable",
                            "field": name,
                            "message": f"Capability {name} is unavailable.",
                        }
                    ],
                )
                records[name] = record
                return record

            capability, origin = capability_with_origin
            effective_enabled = self._enabled_overrides.get(name, capability.default_enabled)
            diagnostics: list[dict[str, str]] = []

            if not effective_enabled:
                status = CapabilityStatus.DISABLED
            elif name in cycle_members:
                status = CapabilityStatus.MISCONFIGURED
                diagnostics.append(
                    {
                        "code": "dependency_cycle",
                        "field": name,
                        "message": f"Capability dependency cycle includes {name}.",
                    }
                )
            else:
                for dependency in capability.dependencies:
                    dependency_record = evaluate(dependency)
                    if dependency_record.origin == CapabilityOrigin.UNAVAILABLE:
                        diagnostics.append(
                            {
                                "code": "dependency_unavailable",
                                "field": dependency,
                                "message": f"Dependency {dependency} is unavailable.",
                            }
                        )
                    elif dependency_record.status == CapabilityStatus.DISABLED:
                        diagnostics.append(
                            {
                                "code": "dependency_disabled",
                                "field": dependency,
                                "message": f"Dependency {dependency} is disabled.",
                            }
                        )
                    elif dependency_record.status == CapabilityStatus.MISCONFIGURED:
                        diagnostics.append(
                            {
                                "code": "dependency_misconfigured",
                                "field": dependency,
                                "message": f"Dependency {dependency} is misconfigured.",
                            }
                        )

                diagnostics.extend(_configuration_diagnostics(capability, self._config_values))
                diagnostics.extend(
                    _query_provider_selection_diagnostics(
                        capability,
                        self._config_values,
                        evaluate,
                    )
                )
                diagnostics.extend(
                    _builtin_configuration_diagnostics(capability, self._config_values)
                )
                status = CapabilityStatus.MISCONFIGURED if diagnostics else CapabilityStatus.ENABLED

            record = CapabilityRecord(
                name=capability.name,
                kind=capability.kind,
                origin=origin,
                default_enabled=capability.default_enabled,
                effective_enabled=effective_enabled,
                dependencies=capability.dependencies,
                configuration=capability.configuration,
                status=status,
                diagnostics=diagnostics,
                description=capability.description,
                version=capability.version,
                owner=capability.owner,
            )
            records[name] = record
            return record

        for name in sorted(names):
            evaluate(name)

        report = CapabilityRegistryReport(capabilities=[records[name] for name in sorted(records)])
        self._last_report = report
        return report


def _capability_map(
    built_in_capabilities: Iterable[Capability], installed_capabilities: Iterable[Capability]
) -> CapabilityMap:
    capabilities: CapabilityMap = {}
    for capability in built_in_capabilities:
        if capability.name in capabilities:
            raise CapabilityValidationError(f"duplicate capability name: {capability.name}")
        capabilities[capability.name] = (
            replace(capability, owner="builtin"),
            CapabilityOrigin.BUILT_IN,
        )
    for capability in installed_capabilities:
        if capability.name in capabilities:
            raise CapabilityValidationError(f"duplicate capability name: {capability.name}")
        capabilities[capability.name] = (capability, CapabilityOrigin.INSTALLED)
    return capabilities


def _configuration_diagnostics(
    capability: Capability, config_values: Mapping[str, str]
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    for requirement in capability.configuration:
        if not requirement.required_when_enabled:
            continue
        value = config_values.get(requirement.key, "")
        if value.strip():
            continue
        label = "secret" if requirement.secret else "configuration"
        diagnostics.append(
            {
                "code": "missing_configuration",
                "field": requirement.key,
                "message": f"Required {label} {requirement.key} is missing.",
            }
        )
    return diagnostics


def _query_provider_selection_diagnostics(
    capability: Capability,
    config_values: Mapping[str, str],
    evaluate: Callable[[str], CapabilityRecord],
) -> list[dict[str, str]]:
    if capability.name != "query-ai":
        return []
    selected = config_values.get("IDEA_INBOX_CHAT_PROVIDER", "").strip()
    if not selected:
        return []
    selected_capability = QUERY_PROVIDER_SELECTIONS.get(selected)
    if selected_capability is None:
        return [
            {
                "code": "unknown_provider_selection",
                "field": "IDEA_INBOX_CHAT_PROVIDER",
                "message": f"Selected chat provider {selected} has no known capability mapping.",
            }
        ]

    record = evaluate(selected_capability)
    if record.origin == CapabilityOrigin.UNAVAILABLE:
        return [
            {
                "code": "dependency_unavailable",
                "field": selected_capability,
                "message": f"Selected provider capability {selected_capability} is unavailable.",
            }
        ]
    if record.status == CapabilityStatus.DISABLED:
        return [
            {
                "code": "dependency_disabled",
                "field": selected_capability,
                "message": f"Selected provider capability {selected_capability} is disabled.",
            }
        ]
    if record.status == CapabilityStatus.MISCONFIGURED:
        return [
            {
                "code": "dependency_misconfigured",
                "field": selected_capability,
                "message": f"Selected provider capability {selected_capability} is misconfigured.",
            }
        ]
    return []


def _builtin_configuration_diagnostics(
    capability: Capability, config_values: Mapping[str, str]
) -> list[dict[str, str]]:
    if capability.name != "sqlite-storage":
        return []
    try:
        load_config(env=config_values)
    except ConfigError as exc:
        return [
            {
                "code": "invalid_configuration",
                "field": DATABASE_URL_ENV,
                "message": str(exc),
            }
        ]
    return []


def _cycle_members(capabilities: CapabilityMap) -> set[str]:
    members: set[str] = set()
    visited: set[str] = set()
    visiting: list[str] = []

    def visit(name: str) -> None:
        if name in visiting:
            cycle_start = visiting.index(name)
            members.update(visiting[cycle_start:])
            return
        if name in visited:
            return
        capability_with_origin = capabilities.get(name)
        if capability_with_origin is None:
            return

        visiting.append(name)
        capability, _origin = capability_with_origin
        for dependency in capability.dependencies:
            visit(dependency)
        visiting.pop()
        visited.add(name)

    for name in capabilities:
        visit(name)
    return members
