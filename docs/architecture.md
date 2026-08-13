# Architecture Overview

Idea Inbox is a self-hosted idea capture and retrieval assistant.

## Core flow

```text
External source → Connector → RawEvent → IdeaDraft → Idea → Indexes → Query → Cited answer
```

The ingestion order is mandatory: raw provider input is stored as `RawEvent` before any draft extraction, normalization, classification, or model call. Derived records can be regenerated from raw events when connector logic changes.

## Stable concepts

- `RawEvent`: immutable-ish provider payload record used for idempotency, auditing, source lineage, and reprocessing.
- `IdeaDraft`: normalized candidate idea extracted from a raw event.
- `Idea`: canonical searchable idea.
- `Connector`: module that maps provider-specific input into raw events and drafts.
- `ModelProvider`: chat/completion provider abstraction.
- `EmbeddingProvider`: embedding provider abstraction.
- `CredentialProvider`: credentials abstraction for API keys, local auth, OAuth/device login, Codex-style login, or proxies.
- `SearchIndex`: keyword/vector/hybrid search abstraction; a derived projection that returns stable idea IDs and ranking metadata.
- `StorageBackend`: authoritative persistence abstraction for `RawEvent`, `IdeaDraft`, `Idea`, and citation lineage.

## Boundary rules

- Dependency direction flows inward: connectors, providers, and adapters depend on core contracts; core domain code does not import connector packages, provider SDK types, search engine clients, or storage driver details.
- `StorageBackend` is the source of truth. Search indexes can be rebuilt and must not become the only place where idea text, raw source metadata, or citation lineage exists.
- Generated answers cite persisted `Idea` records, and those citations must remain traceable to the raw source event and provider/source IDs used to derive the idea.
- Credential lifecycle belongs behind `CredentialProvider`; model and embedding providers do not own secret storage, OAuth refresh, proxy login, or local login persistence.

## Current search projection

The first implemented search adapter is SQLite FTS5. Migration `0002_idea_fts.sql` creates an
`idea_fts` virtual table over canonical idea text, normalized tags, and `source_ref`, backed by
the `ideas` table with `content='ideas'` and synchronized by insert/update/delete triggers.
Raw event payloads are preserved for audit and reprocessing, but they are not indexed by the
current search projection.

`GET /v1/ideas/search` returns stable idea IDs, snippets, scores, source, and capture time from
the joined `ideas` row. Query answers must continue to resolve search hits back through stored
ideas before presenting citations.

## Design priorities

1. Lightweight default deployment.
2. Contributor-friendly extension points.
3. Local AI and OAuth/proxy model flows must be addable without rewrites.
4. Retrieval answers must include citations.
5. Raw source data must be preserved separately from normalized ideas.
