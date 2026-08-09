# ADR-001: Connector and provider plugin boundaries

## Status
Accepted

## Context

Idea Inbox must support many future inputs, AI backends, storage engines, and search implementations without full rewrites. The MVP architecture spec defines the core flow as `External source → Connector → RawEvent → IdeaDraft → Idea → Indexes → Query → Cited answer` and requires core services to depend on SDK-free domain models and narrow ports.

See [`../specs/mvp-architecture-spec.md`](../specs/mvp-architecture-spec.md), especially the architecture overview, core service interfaces, provider design, connector design, and MVP acceptance criteria.

## Decision

Define stable interfaces for connectors, model providers, embedding providers, credential providers, search indexes, and storage backends from the beginning.

Core domain code may depend on plain models and protocol definitions only. Connector, provider, storage, search, and HTTP adapters depend inward on those contracts and must not leak provider SDK objects, database driver types, webhook framework objects, or credential implementation details into core ingestion/query services.

## Consequences

- Initial MVP may take slightly longer because ports and dependency injection must be designed before adapters are fully implemented.
- Contributors can add platforms, providers, storage engines, or search implementations without understanding the whole system.
- Core domain logic stays stable as integrations evolve.
- Tests should enforce boundary rules with mocks/fixtures and should fail if core imports adapter SDKs or drivers.
