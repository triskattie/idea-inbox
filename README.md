# Idea Inbox

Self-hosted idea capture and retrieval assistant for collecting ideas from chat, email, webhooks, and other inboxes, then querying them later with cited answers.

## Goals

- Easy self-hosting with a lightweight default path.
- Contributor-friendly architecture and documentation.
- Stable extension points for connectors, model providers, embedding providers, credential providers, storage, and search.
- No lock-in to OpenAI API keys: local AI, OpenAI-compatible endpoints, OAuth/proxy/Codex-style flows should be addable without rewrites.

## Planned MVP

1. Manual API idea capture.
2. Raw event ingestion pipeline.
3. SQLite default storage and full-text search.
4. Provider interfaces for embeddings and answer generation.
5. Cited query endpoint.
6. Telegram, email, and Discord connectors.
7. Optional Postgres + pgvector production profile.

## Development status

This repository is currently being initialized. See:

- [Development standards](CONTRIBUTING.md)
- [Architecture overview](docs/architecture.md)
- [ADRs](docs/decisions/)
- [Initial project spec](docs/specs/initial-product-spec.md)

## Quick start

```bash
uv sync
cp .env.example .env
uv run idea-inbox dev
```

The implementation will keep SQLite as the zero-friction default and Docker Compose as the self-host path.
