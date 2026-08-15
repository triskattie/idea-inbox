# Connector Guide

Connectors ingest messages from external systems.

## Contract

A connector should:

1. Validate provider payloads at the boundary.
2. Preserve provider IDs for idempotency.
3. Store the provider-specific payload as a durable `RawEvent` before extraction or normalization.
4. Extract zero or more `IdeaDraft` objects from stored `RawEvent` records.
5. Avoid provider SDK types leaking into core modules.

Connectors may depend on core domain contracts, but core domain code must not depend on connector packages, provider SDKs, webhook framework types, or third-party account clients. If extraction rules change, drafts should be regenerated from stored raw events rather than by replaying external provider APIs.

## Implemented connectors

- Manual API (`POST /v1/ideas`) stores user-submitted ideas as `manual` raw events before
  creating derived drafts and canonical ideas.

## Planned connectors

- Generic webhook
- Telegram
- Email/IMAP
- Discord
- WhatsApp Cloud API later

Unofficial account-scraping connectors are not allowed in core. Connectors should prefer official APIs, export formats, or user-submitted webhooks; any risky third-party scraping adapter must remain optional, isolated, and unable to bypass raw-event preservation.
