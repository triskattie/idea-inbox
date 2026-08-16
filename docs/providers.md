# Provider Guide

Providers supply model, embedding, and credential capabilities without leaking provider-specific SDKs or auth flows into the core domain.

## Model providers

Current implementation status: model and embedding provider config keys are reserved but not
loaded by `src/idea_inbox/config.py` yet. `.env.example` includes
`IDEA_INBOX_CHAT_PROVIDER`, `IDEA_INBOX_EMBEDDING_PROVIDER`, `IDEA_INBOX_OPENAI_BASE_URL`,
`IDEA_INBOX_OPENAI_API_KEY`, `IDEA_INBOX_OPENAI_CHAT_MODEL`, and
`IDEA_INBOX_OPENAI_EMBEDDING_MODEL` to show the planned shape; setting them does not enable
provider-backed answer generation in the current runtime.

The core must not assume OpenAI API keys. Supported paths should include:

- mock provider for tests
- OpenAI-compatible HTTP provider
- Ollama/local provider
- local sentence-transformer embedding provider
- OAuth/proxy/Codex-style credential flows later

Model and embedding providers own generation/embedding API calls and provider-specific request mapping only. They request secrets or session material through `CredentialProvider`; they do not store secrets, refresh OAuth tokens, run browser login flows, or decide how credentials are persisted.

## Credential providers

Credential providers allow a model provider to request credentials without knowing where they came from. They own credential lookup, refresh, and persistence policy for API-key, local, OAuth/device-code, proxy, and Codex-style login paths.

Initial providers can be simple:

- `none`
- `env_api_key`
- `static_config`

Future providers:

- `oauth_device_code`
- `codex_login`
- `hermes_proxy`
- `browser_login`

Core contracts should accept credential handles or resolved request auth data, not provider SDK credential objects, so future auth paths remain swappable.
