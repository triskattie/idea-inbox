# Self-hosting

Target deployment modes:

## Lightweight local

SQLite, built-in API, mock or local providers.

```bash
docker run -v idea-inbox-data:/data -p 8080:8080 ghcr.io/triskattie/idea-inbox:latest
```

## Recommended production

Docker Compose with Postgres + pgvector.

```bash
docker compose up -d
```

No production setup should require a paid hosted model. Hosted models may be optional accelerators.
