# Connector Guide

Connectors are optional modules that ingest messages from external systems. The manual API is the only built-in capture path required by the base app.

## Contract

A connector should:

1. Validate provider payloads at the boundary.
2. Preserve provider IDs for idempotency.
3. Store the provider-specific payload as a durable `RawEvent` before extraction or normalization.
4. Extract zero or more `IdeaDraft` objects from stored `RawEvent` records.
5. Avoid provider SDK types leaking into core modules.

Adapters implement the SDK-free `Connector` protocol in
`idea_inbox.core.ports`: `validate(payload, headers, credentials)` returns a
`ValidatedConnectorEvent` carrying a `RawEventInput`, `to_raw_event_input()` exposes that raw
event input to core, and `extract_drafts(raw_event)` derives drafts from a stored raw event.
The shared ingestion service `idea_inbox.core.services.ingest_connector_event` persists the raw
event first, is idempotent by `(source, dedupe_key)`, and returns the existing lineage on
replays (`duplicate=True`). Connectors may depend on core domain contracts, but core domain code
must not depend on connector packages, provider SDKs, webhook framework types, or third-party
account clients. If extraction rules change, drafts should be regenerated from stored raw events
rather than by replaying external provider APIs.

## Implemented connectors

- Manual API (`POST /v1/ideas`) stores user-submitted ideas as `manual` raw events before
  creating derived drafts and canonical ideas.
- Generic webhook connector (`idea_inbox.connectors.webhook.GenericWebhookConnector`) validates
  source-agnostic JSON idea events and preserves verbatim `event_id` values (or a payload hash
  when absent) as idempotency keys. Its HTTP route
  `POST /v1/connectors/webhook/generic` exists but returns `503 CAPABILITY_DISABLED` unless the
  built-in `generic-webhook-connector` capability is enabled through an injected registry.
- Telegram fixture connector (`idea_inbox.connectors.telegram.TelegramConnector`) parses Bot API
  update payloads offline and preserves `update_id` for idempotency. No network calls.
- Email fixture connector (`idea_inbox.connectors.email.EmailConnector`) parses raw RFC 5322
  messages supplied by tests or callers while preserving `Message-ID` as the idempotency key.
  It does not open IMAP connections.
- Discord fixture connector (`idea_inbox.connectors.discord.DiscordConnector`) parses gateway
  `MESSAGE_CREATE` payloads offline and preserves Discord message IDs for idempotency. No network
  calls.

Current implementation status: `.env.example` includes planned connector/auth keys, but only the
manual API and the capability-gated generic webhook have HTTP surfaces today. Telegram, email,
and Discord adapters are fixture/payload parsers without runtimes or polling daemons.
`IDEA_INBOX_API_KEY` is not enforced yet, and `IDEA_INBOX_TELEGRAM_BOT_TOKEN`,
`IDEA_INBOX_DISCORD_BOT_TOKEN`, `IDEA_INBOX_EMAIL_IMAP_URL`, `IDEA_INBOX_EMAIL_USERNAME`, and
`IDEA_INBOX_EMAIL_PASSWORD` are reserved until those connector runtimes land.

## Planned connectors

- Generic webhook signature/token validation
- Telegram polling/webhook runtime
- Email/IMAP polling/runtime
- Discord bot/gateway runtime
- WhatsApp Cloud API later

Unofficial account-scraping connectors are not allowed in core. Connectors should prefer official APIs, export formats, or user-submitted webhooks; any risky third-party scraping adapter must remain optional, isolated, and unable to bypass raw-event preservation.
