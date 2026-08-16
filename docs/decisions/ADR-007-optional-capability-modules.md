# ADR-007: Keep AI and heavyweight integrations as optional capability modules

## Status
Accepted

## Date
2026-08-16

## Context

Idea Inbox should remain a lightweight self-hosted program that is useful without AI, hosted model accounts, vector databases, platform bot tokens, or other integrations that some operators will not want. The current core already supports manual capture and SQLite FTS search without hosted credentials or hidden outbound calls. The next planned cited-query work would add answer generation; if that is treated as mandatory core behavior, it risks turning a simple capture/search tool into an AI-first product by default.

The project has no external users yet, so the module system does not need to be fully implemented before every next feature. However, the intended direction must be explicit now so near-term implementation does not bake AI, providers, connectors, or future heavy dependencies into core startup, configuration, tests, or release expectations.

## Decision

Keep the base application focused on local capture, raw-event preservation, SQLite storage, and keyword search. AI-assisted cited query, embeddings/hybrid search, hosted model providers, platform connectors, Postgres/pgvector, richer auth flows, and similar nonessential capabilities are optional modules that an operator installs and enables deliberately.

The module system will be introduced incrementally:

1. **Now:** document the product rule and keep provider/connector settings reserved or no-op unless an implementation is explicitly enabled.
2. **Next development phase:** define a lightweight capability/module contract and registry without requiring third-party providers or changing the default install path.
3. **After the contract exists:** move cited natural-language query behind an optional `query-ai` capability/module. The default app can still expose capture and keyword search without AI.
4. **Later:** add installable modules for embeddings/hybrid search, connectors, hosted/local model providers, Postgres/pgvector profiles, and other heavier features.

Until the module contract lands, any AI/query implementation must be deterministic/local in tests, disabled unless explicitly configured, and isolated behind provider interfaces so it can be moved into a module without rewriting core services.

## Consequences

- The core product remains useful to operators who only want capture and search.
- AI is not a prerequisite for installation, startup, tests, or basic self-hosting.
- Cited query remains a product goal, but it is no longer treated as unavoidable core behavior.
- Phase planning must include module boundaries before feature work that would otherwise pull AI or heavyweight dependencies into the base app.
- Documentation must clearly distinguish current core capabilities, planned optional modules, and disabled/reserved configuration keys.
