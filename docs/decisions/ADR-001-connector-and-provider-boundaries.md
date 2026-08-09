# ADR-001: Connector and provider plugin boundaries

## Status
Accepted

## Context

Idea Inbox must support many future inputs and AI backends without full rewrites.

## Decision

Define stable interfaces for connectors, model providers, embedding providers, credential providers, search indexes, and storage backends from the beginning.

## Consequences

- Initial MVP may take slightly longer.
- Contributors can add platforms/providers without understanding the whole system.
- Core domain logic stays stable as integrations evolve.
