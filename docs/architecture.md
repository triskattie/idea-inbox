# Architecture Overview

Idea Inbox is a self-hosted idea capture and retrieval assistant.

## Core flow

```text
External source → Connector → RawEvent → IdeaDraft → Idea → Indexes → Query → Cited answer
```

## Stable concepts

- `RawEvent`: immutable-ish provider payload record used for idempotency, auditing, and reprocessing.
- `IdeaDraft`: normalized candidate idea extracted from a raw event.
- `Idea`: canonical searchable idea.
- `Connector`: module that maps provider-specific input into raw events and drafts.
- `ModelProvider`: chat/completion provider abstraction.
- `EmbeddingProvider`: embedding provider abstraction.
- `CredentialProvider`: credentials abstraction for API keys, local auth, OAuth/device login, Codex-style login, or proxies.
- `SearchIndex`: keyword/vector/hybrid search abstraction.
- `StorageBackend`: persistence abstraction.

## Design priorities

1. Lightweight default deployment.
2. Contributor-friendly extension points.
3. Local AI and OAuth/proxy model flows must be addable without rewrites.
4. Retrieval answers must include citations.
5. Raw source data must be preserved separately from normalized ideas.
