# Spec: Idea Inbox Initial Product

## Objective

Build a lightweight self-hosted idea capture and retrieval assistant. Users can send ideas from multiple channels and later query their own ideas with cited answers.

## Success criteria

- Easy single-user self-hosting.
- Contributor-friendly codebase and docs.
- Manual idea capture works before platform connectors.
- Raw events and normalized ideas are stored separately.
- Query answers cite retrieved ideas.
- Local AI and OAuth/proxy auth paths can be added without rewrites.

## MVP phases

1. Project skeleton and standards.
2. Manual idea API.
3. Raw event pipeline.
4. Keyword search.
5. Embeddings and hybrid search.
6. Cited query endpoint.
7. Telegram/email/Discord connectors.
8. Optional Postgres + pgvector deployment profile.

## Out of scope for MVP

- Full web app UI.
- Multi-user permissions.
- Unofficial WhatsApp scraping.
- Complex autonomous workflows.
