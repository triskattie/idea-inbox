# Spec: Idea Inbox Initial Product

## Objective

Build a lightweight self-hosted idea capture and retrieval assistant. Users can capture and search ideas without AI, then optionally install or enable modules for cited AI-assisted query and additional integrations.

## Success criteria

- Easy single-user self-hosting.
- Contributor-friendly codebase and docs.
- Manual idea capture works before platform connectors.
- Raw events and normalized ideas are stored separately.
- Keyword search works without AI or hosted credentials.
- Query answers cite retrieved ideas when the optional query capability is enabled.
- Local AI and OAuth/proxy auth paths can be added without rewrites.
- AI, embeddings, connectors, and heavier deployment profiles are explicit opt-in modules rather than default requirements.

## MVP phases

1. Project skeleton and standards.
2. Manual idea API.
3. Raw event pipeline.
4. Keyword search.
5. Capability/module contract and registry plan.
6. Optional cited query capability/module.
7. Optional embeddings and hybrid search module.
8. Optional Telegram/email/Discord connector modules.
9. Optional Postgres + pgvector deployment profile.

## Out of scope for MVP

- Full web app UI.
- Multi-user permissions.
- Unofficial WhatsApp scraping.
- Complex autonomous workflows.
- Requiring AI, hosted model accounts, platform connector credentials, or vector databases for the base app.
