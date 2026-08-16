"""SDK-free capability metadata contracts."""

import re
from dataclasses import dataclass, field
from enum import StrEnum

CAPABILITY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class CapabilityValidationError(ValueError):
    """Raised when capability metadata violates the public contract."""


class CapabilityKind(StrEnum):
    """Known capability categories."""

    CORE = "core"
    QUERY = "query"
    PROVIDER = "provider"
    CONNECTOR = "connector"
    SEARCH = "search"
    STORAGE = "storage"


class CapabilityOrigin(StrEnum):
    """Where capability metadata came from."""

    BUILT_IN = "built-in"
    INSTALLED = "installed"
    UNAVAILABLE = "unavailable"


class CapabilityStatus(StrEnum):
    """Operational readiness of a capability."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    MISCONFIGURED = "misconfigured"


@dataclass(frozen=True)
class ConfigRequirement:
    """Configuration or credential handle required by a capability."""

    key: str
    required_when_enabled: bool
    secret: bool
    description: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise CapabilityValidationError("configuration key must not be empty")
        if not self.description.strip():
            raise CapabilityValidationError("configuration description must not be empty")


@dataclass(frozen=True)
class Capability:
    """Immutable SDK-free capability metadata."""

    name: str
    kind: CapabilityKind
    dependencies: tuple[str, ...] = ()
    default_enabled: bool = False
    configuration: tuple[ConfigRequirement, ...] = ()
    description: str = ""
    version: str | None = None
    owner: str = "builtin"

    def __post_init__(self) -> None:
        _validate_capability_name(self.name)
        for dependency in self.dependencies:
            _validate_capability_name(dependency)
        if len(set(self.dependencies)) != len(self.dependencies):
            raise CapabilityValidationError(f"capability {self.name} has duplicate dependencies")
        if not self.owner.strip():
            raise CapabilityValidationError("capability owner must not be empty")


@dataclass(frozen=True)
class CapabilityRecord:
    """Validated registry view of a capability."""

    name: str
    kind: CapabilityKind | None
    origin: CapabilityOrigin
    default_enabled: bool
    effective_enabled: bool
    dependencies: tuple[str, ...]
    configuration: tuple[ConfigRequirement, ...]
    status: CapabilityStatus
    diagnostics: list[dict[str, str]] = field(default_factory=list)
    description: str = ""
    version: str | None = None
    owner: str | None = None


@dataclass(frozen=True)
class CapabilityRegistryReport:
    """Complete capability validation report."""

    capabilities: list[CapabilityRecord]

    @property
    def diagnostics(self) -> list[dict[str, str]]:
        """Flatten diagnostics from all capability records."""
        return [diagnostic for record in self.capabilities for diagnostic in record.diagnostics]


def _validate_capability_name(name: str) -> None:
    if not CAPABILITY_NAME_PATTERN.fullmatch(name):
        raise CapabilityValidationError(
            "capability names must be lowercase kebab-case slugs starting with a letter"
        )
