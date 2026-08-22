# Spec: Capability/module contract and registry

## Status

Implemented in Phase 5 for the SDK-free metadata contract and in-process registry. Phase 7 adds
explicit provider capability declarations and adapter boundaries using the same registry shape.
Later phases may add public HTTP/CLI surfaces, package discovery, connector runtimes, secret
persistence, OAuth/device-login flows, or automatic provider construction from environment.

## Objective

Define the small capability contract needed before cited AI query, embeddings, hosted/local providers, platform connectors, or heavier storage profiles become user-facing. The registry should make optional behavior visible and validatable while keeping the base app useful with only manual capture, SQLite storage, and FTS-backed keyword search.

## Scope

In scope for Phase 5:

- Plain, SDK-free capability metadata.
- Runtime registry construction from built-in metadata plus any explicitly installed modules known to the process.
- Dependency and configuration validation that reports state without starting optional clients or making network calls.
- API/service contracts that later HTTP or CLI surfaces can expose.

Out of scope for Phase 5:

- No AI query endpoint in Phase 5 itself; v0.2.0 adds a separate default-disabled deterministic query foundation. Still out of scope for the registry are real model calls, embeddings, vector search, platform connector runtimes, plugin marketplace, package installer, or module hot-loading.
- No secret persistence or OAuth/device-login implementation.
- No requirement for third-party dependencies in the base install.

## Capability metadata shape

Represent each capability as an immutable plain record, implemented as a dataclass or equivalent typed model in core code. The minimum fields are:

| Field | Shape | Meaning |
| --- | --- | --- |
| `name` | stable slug string | Unique identifier such as `core`, `manual-capture`, `sqlite-storage`, `sqlite-fts-search`, `query-ai`, `openai-compatible-model-provider`, or `telegram-connector`. Use lowercase kebab-case and treat names as public API. |
| `kind` | enum/string | Category: `core`, `query`, `provider`, `connector`, `search`, or `storage`. Future kinds are additive. |
| `dependencies` | list of capability names | Other capabilities that must be installed and enabled before this one can be enabled. Keep dependencies capability-level, not Python package names. |
| `default_enabled` | bool | Whether the capability is enabled when present and no operator override exists. Core/base capabilities may default to `true`; AI, embeddings, external providers, platform connectors, and heavier deployment profiles default to `false`. |
| `configuration` | list of config requirements | Non-secret config required for validation, plus credential handles when secrets are needed. Requirements identify config keys and whether they are required only when enabled. |

Recommended non-minimum fields for implementation ergonomics:

- `description`: one human-readable sentence for CLI/API display.
- `version`: module contract version or package version if available.
- `owner`: `builtin` or installed module/package identifier.

Configuration requirement records should include:

| Field | Meaning |
| --- | --- |
| `key` | Public config key or credential handle name, for example `IDEA_INBOX_CHAT_PROVIDER`. |
| `required_when_enabled` | `true` when missing/invalid values make an enabled capability misconfigured. |
| `secret` | `true` for credentials; registry output must report presence/absence only, never values. |
| `description` | Short operator-facing explanation. |

## Lifecycle and status vocabulary

The registry distinguishes origin/presence from operational status.

Origin/presence vocabulary:

- `built-in`: Capability metadata ships with the base package and is always discoverable.
- `installed`: Capability metadata is discoverable from an explicitly installed module/package or configured adapter. Installed does not imply enabled.
- `unavailable`: Capability is referenced by configuration or dependencies, but metadata or required import/runtime support is not present.

Operational status vocabulary:

- `enabled`: Capability is present, operator policy says enabled, dependencies are enabled, and required configuration is valid.
- `disabled`: Capability is present but operator policy or `default_enabled=false` leaves it inactive. Disabled capabilities must not perform startup work, network calls, migrations, provider calls, or connector polling.
- `misconfigured`: Capability is enabled by policy but has missing/invalid configuration or credential handles, or one of its dependencies is missing, disabled, unavailable, or misconfigured.

A capability can be both `built-in` and `enabled`, or `installed` and `disabled`. Public API records should expose origin and status separately instead of collapsing them into one string.

## Dependency and configuration validation

Registry validation should be deterministic and side-effect-light:

1. Load built-in capability metadata from code.
2. Load installed capability metadata from explicitly configured/discoverable modules, but do not initialize provider SDKs, connector clients, database pools, or network sessions.
3. Compute effective enabled policy: operator override if present, otherwise `default_enabled`.
4. Validate dependencies by capability name:
   - Missing dependency metadata => current capability `misconfigured`; dependency appears as `unavailable` in diagnostics.
   - Dependency present but disabled => current capability `misconfigured` with a dependency-disabled reason.
   - Dependency present but misconfigured/unavailable => current capability `misconfigured` with dependency status in diagnostics.
   - Cycles are invalid and must mark participating capabilities `misconfigured`.
5. Validate configuration requirements only for enabled capabilities. Reserved provider/connector settings remain inert while their owning capability is disabled.
6. Never print or return secret values. Report only requirement key, present/missing/invalid, and a human-readable reason.

Validation should return a complete report, not fail fast, so operators and tests can see every blocker in one response.

## Registry API contract

Place the initial registry in core/application-level code so optional adapters depend inward instead of core importing adapter implementations:

```text
src/idea_inbox/core/capabilities.py       Capability, ConfigRequirement, status enums
src/idea_inbox/core/ports.py              Optional CapabilityRegistry protocol if needed
src/idea_inbox/capabilities/registry.py   Built-in metadata and validation orchestration
```

Do not put provider SDK imports, connector SDK imports, or plugin package discovery in `idea_inbox.core`.

The implemented files are:

- `src/idea_inbox/core/capabilities.py`: `Capability`, `ConfigRequirement`, `CapabilityRecord`,
  `CapabilityRegistryReport`, and status/origin/kind enums.
- `src/idea_inbox/capabilities/registry.py`: built-in capability metadata and
  `CapabilityRegistry` validation orchestration.
- `tests/test_capability_registry.py`: contract tests for defaults, installed capabilities,
  dependency diagnostics, configuration diagnostics, unavailable references, and cycles.

The registry service should expose:

- `list_capabilities() -> list[CapabilityRecord]`: all known capabilities with origin, effective enabled state, status, and diagnostics.
- `get_capability(name: str) -> CapabilityRecord | None`: one record by stable name.
- `is_enabled(name: str) -> bool`: convenience gate for API/CLI startup paths; returns `false` for disabled, unavailable, or misconfigured capabilities.
- `validate() -> CapabilityRegistryReport`: full validation result with diagnostics and no side effects beyond reading configuration and metadata.

A future HTTP or CLI surface can expose the same report shape, but Phase 5 does not require a public endpoint. If an endpoint is later added, it should be read-only and must redact secrets.

Example installed capability registration:

```python
from idea_inbox.capabilities.registry import CapabilityRegistry
from idea_inbox.core.capabilities import Capability, CapabilityKind, ConfigRequirement

provider = Capability(
    name="openai-compatible-model-provider",
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
record = registry.get_capability("openai-compatible-model-provider")
```

## Built-in baseline capabilities

Phase 5 should define at least these built-in records:

| Name | Kind | Default | Notes |
| --- | --- | --- | --- |
| `core` | `core` | enabled | Base domain models, config loading, CLI skeleton. |
| `manual-capture` | `connector` | enabled | Current `POST /v1/ideas` manual input path; depends on `core` and configured storage. |
| `sqlite-storage` | `storage` | enabled | Current default persistence path; requires valid SQLite database location. |
| `sqlite-fts-search` | `search` | enabled | Current keyword search projection; depends on `sqlite-storage`. |
| `query-ai` | `query` | disabled | Planned cited natural-language query; depends on search plus a model provider. |

Phase 7 provider records such as `model-provider`, `mock-model-provider`,
`openai-compatible-model-provider`, `ollama-model-provider`, `embedding-provider`,
`none-credentials`, `env-api-key-credentials`, and `static-config-credentials` are installed only
when explicitly supplied to `CapabilityRegistry(installed_capabilities=...)`; they default disabled
and must not become base runtime prerequisites. Future connector records such as
`telegram-connector`, `email-imap-connector`, and `discord-connector` follow the same rule.

## Example capability record

```json
{
  "name": "query-ai",
  "kind": "query",
  "origin": "built-in",
  "default_enabled": false,
  "effective_enabled": false,
  "dependencies": ["sqlite-fts-search", "model-provider"],
  "configuration": [
    {
      "key": "IDEA_INBOX_CHAT_PROVIDER",
      "required_when_enabled": true,
      "secret": false,
      "description": "Selects the enabled chat/model provider capability."
    }
  ],
  "status": "disabled",
  "diagnostics": []
}
```

An enabled but incomplete provider might report:

```json
{
  "name": "openai-compatible-model-provider",
  "kind": "provider",
  "origin": "installed",
  "default_enabled": false,
  "effective_enabled": true,
  "dependencies": ["core", "env-api-key-credentials"],
  "configuration": [
    {
      "key": "IDEA_INBOX_OPENAI_BASE_URL",
      "required_when_enabled": true,
      "secret": false,
      "description": "OpenAI-compatible API base URL."
    },
    {
      "key": "IDEA_INBOX_OPENAI_API_KEY",
      "required_when_enabled": true,
      "secret": true,
      "description": "Credential handle supplied by a credential provider."
    }
  ],
  "status": "misconfigured",
  "diagnostics": [
    {
      "code": "missing_configuration",
      "field": "IDEA_INBOX_OPENAI_API_KEY",
      "message": "Credential is required when openai-compatible-model-provider is enabled."
    }
  ]
}
```

## Assumptions and non-goals

- Built-in SQLite storage, FTS search, and manual capture remain enabled by default because they are the lightweight MVP path.
- AI query, embeddings, external connectors, hosted/local model providers, credential flows, Postgres/pgvector, and other heavier features stay disabled until deliberately enabled.
- Configuration overrides can come from environment variables or future config files; the registry contract should not require one storage mechanism.
- The registry reports capability readiness; it does not own business logic, migrations, model prompts, connector polling loops, package installation, or secret storage.
- Future installable modules can map package metadata into the same internal records, but Phase 5 should avoid committing to Python entry points, plugin marketplaces, or hot-reload semantics until a later spec accepts that packaging format.

## Acceptance checklist for implementation workers

- Capability metadata includes name, kind, dependencies, default-enabled state, and configuration requirements.
- Status reporting covers built-in, installed, enabled, disabled, unavailable, and misconfigured states without conflating origin and operational status.
- Dependency validation reports missing, disabled, unavailable, misconfigured, and cyclic dependencies.
- Configuration validation runs only for effectively enabled capabilities and redacts secrets.
- Registry API can list, fetch, check enabled state, and return a full validation report.
- Code lives behind core/application contracts and keeps provider/connector implementations isolated from core domain code.
- Startup, migration, manual capture, and FTS search still work with no optional capabilities enabled.
- Reserved provider/connector settings stay inert until their owning capability is enabled.
