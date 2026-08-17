# ADR-003: Retrieval answers require citations

## Status
Accepted

## Context

The assistant must answer from the user's captured ideas, not invent project memory. The MVP architecture spec requires `/v1/query` to retrieve stored ideas before answer generation, cite persisted ideas when evidence exists, and return an explicit no-evidence response when retrieval finds no relevant ideas. The v0.2.0 cited-query API contract turns that decision into a testable request/response and citation contract.

See [`../specs/mvp-architecture-spec.md`](../specs/mvp-architecture-spec.md) and [`../specs/cited-query-api-contract.md`](../specs/cited-query-api-contract.md), especially the query API, citation contract, capability-disabled response, and provenance requirements.

## Decision

Generated query answers must cite the persisted ideas used as evidence. If no relevant ideas are found, the assistant must say so.

Search indexes are retrieval aids, not evidence stores. They may return ranked IDs, snippets, and metadata, but answer generation must resolve citations through `StorageBackend` so each cited `Idea` remains traceable to its source `RawEvent` and provider/source identifiers.

## Consequences

- Query quality is easier to debug.
- Users can trace answers back to source messages.
- Prompting and tests must enforce retrieval-only answer behavior.
- Citation tests must fail if answers cite only index fragments, derived summaries without idea IDs, or records that cannot be traced back to stored raw source lineage.
