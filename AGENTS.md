# Agent Instructions

Follow the project standards in `CONTRIBUTING.md`.

Non-negotiables:

1. Use spec-first and TDD for behavior changes.
2. Keep connector/provider code isolated from core domain code.
3. Preserve raw events before normalizing ideas.
4. Generated answers must cite stored ideas.
5. Keep SQLite dev mode healthy.
6. Do not design API-key-only model paths; credential providers must allow OAuth/proxy/local flows later.
7. Update docs/ADRs when architectural decisions change.
8. Do not commit secrets or `.env` files.
