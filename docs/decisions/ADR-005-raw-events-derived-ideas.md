# ADR-005: Raw events are preserved and ideas are derived

## Status
Accepted

## Context

Connectors may change, classifiers may improve, dedupe bugs may need investigation, and generated answers must remain traceable to stored source material. The MVP architecture spec makes `RawEvent` persistence the first step in ingestion before draft extraction, normalization, indexing, embeddings, or model calls.

See [`../specs/mvp-architecture-spec.md`](../specs/mvp-architecture-spec.md), especially the domain models, storage design, connector design, and manual ingestion phase acceptance criteria.

## Decision

Every external message is first stored as a raw event before draft extraction, normalization, classification, embedding, or model calls. Normalized `IdeaDraft` and `Idea` records are derived records that can be regenerated from stored raw events.

## Consequences

- Storage uses more space.
- Ingestion is debuggable and idempotent.
- Future enrichment can reprocess historical events.
- Connectors must preserve provider/source IDs and raw payload metadata needed for citation lineage and dedupe.
- Extraction logic must not rely on replaying external provider APIs when a stored raw event is sufficient.
