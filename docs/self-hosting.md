# Self-hosting

Target deployment modes, separated by what is available now versus what is planned.

## Current local smoke setup

The repository is currently in initialization. The available local path is a smoke setup
that installs the package and runs the placeholder CLI with SQLite-oriented configuration
and mock/local providers.

```bash
uv sync
cp .env.example .env
uv run idea-inbox
```

Local/mock mode is the privacy-preserving default for development: it must not require
hosted-model credentials, hidden outbound model calls, or telemetry. Hosted model providers
may be configured explicitly later, but they are optional accelerators rather than a
requirement for local development.

## Planned lightweight self-hosting

The intended lightweight self-host path is SQLite, the built-in API, and mock or local
providers packaged for a single host. A Docker image may become the convenient packaging
format once the repository includes a Dockerfile and a published image exists.

## Planned production self-hosting

The intended production profile is Docker Compose with Postgres + pgvector and explicit
provider configuration. Do not use Docker or Compose commands from this documentation until
matching repository assets exist, such as a `Dockerfile`, a Compose file, and/or a confirmed
published image.

No production setup should require a paid hosted model. Hosted models may be optional accelerators.
