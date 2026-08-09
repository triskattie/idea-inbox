# ADR-006: MVP scope is local-first and intentionally narrow

## Status
Accepted

## Context

Idea Inbox is intended to be a lightweight, self-hosted assistant for capturing and querying personal ideas. The MVP architecture spec narrows that goal to a single-operator local deployment with manual capture, raw-event preservation, SQLite storage, FTS-backed search, cited query answers, provider/connector interfaces, and optional hosted providers only when explicitly configured.

The spec also names exclusions that would otherwise pull the architecture toward a SaaS product or fragile integration surface: full web UI, multi-user accounts/permissions, unofficial account scraping, complex autonomous workflows, required paid hosted models, and production-only infrastructure as the default path.

See [`../specs/mvp-architecture-spec.md`](../specs/mvp-architecture-spec.md), especially the product goal, non-goals, user-facing MVP scope, privacy/security assumptions, self-hosting configuration, and future work sections.

## Decision

Treat the MVP as a local-first, single-operator system with a versioned HTTP API and contributor-friendly extension contracts. The default development path must run with SQLite and mock/local providers, without requiring hosted-model credentials, outbound model calls, Docker, Postgres, pgvector, OAuth/device login, or platform connector credentials.

Manual API capture is the first complete ingestion path. Generic webhook, Telegram, email/IMAP, and Discord connectors are implemented as isolated connector modules after the ingestion contract is exercised. Postgres + pgvector, richer local/vector search, OAuth-style credential providers, UI, multi-user authorization, retention/redaction, and additional official connectors remain future work behind the chosen interfaces.

## Consequences

- The MVP can be verified by contributors on a single machine with deterministic tests and no paid services.
- Documentation must distinguish implemented local commands from planned Docker/production assets until those files exist.
- Single-operator assumptions are explicit; API field names may leave room for future ownership, but the MVP must not claim multi-user security semantics.
- Hosted providers and production databases are optional accelerators, not prerequisites or default architecture.
- Feature proposals that require scraping accounts, broad UI work, RBAC, autonomous workflows, or production-only infrastructure should be deferred or specified separately rather than folded into the MVP.
