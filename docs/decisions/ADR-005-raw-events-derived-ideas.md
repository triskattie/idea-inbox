# ADR-005: Raw events are preserved and ideas are derived

## Status
Accepted

## Context

Connectors may change, classifiers may improve, and dedupe bugs may need investigation.

## Decision

Every external message is first stored as a raw event. Normalized ideas are derived records that can be regenerated.

## Consequences

- Storage uses more space.
- Ingestion is debuggable and idempotent.
- Future enrichment can reprocess historical events.
