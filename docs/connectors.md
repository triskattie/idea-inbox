# Connector Guide

Connectors ingest messages from external systems.

## Contract

A connector should:

1. Validate provider payloads at the boundary.
2. Preserve provider IDs for idempotency.
3. Map provider-specific payloads to `RawEvent`.
4. Extract zero or more `IdeaDraft` objects.
5. Avoid provider SDK types leaking into core modules.

## Planned connectors

- Manual API
- Generic webhook
- Telegram
- Email/IMAP
- Discord
- WhatsApp Cloud API later

Unofficial account-scraping connectors are not allowed in core.
