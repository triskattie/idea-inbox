# Connector Guide

Connectors are optional modules that ingest messages from external systems. The manual API is the only built-in capture path required by the base app.

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

Current implementation status: `.env.example` includes planned connector/auth keys, but only the
manual API runtime exists today. `IDEA_INBOX_API_KEY` is not enforced by `POST /v1/ideas` yet, and
`IDEA_INBOX_TELEGRAM_BOT_TOKEN`, `IDEA_INBOX_DISCORD_BOT_TOKEN`, `IDEA_INBOX_EMAIL_IMAP_URL`,
`IDEA_INBOX_EMAIL_USERNAME`, and `IDEA_INBOX_EMAIL_PASSWORD` are reserved until those connector
runtimes land.

## Planned connectors

- Generic webhook
- Telegram
- Email/IMAP
- Discord
- WhatsApp Cloud API later

Unofficial account-scraping connectors are not allowed in core. Connectors should prefer official APIs, export formats, or user-submitted webhooks; any risky third-party scraping adapter must remain optional, isolated, and unable to bypass raw-event preservation.
