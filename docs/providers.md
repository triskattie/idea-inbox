# Provider Guide

Providers supply model, embedding, and credential capabilities without leaking provider-specific SDKs or auth flows into the core domain.

## Model providers

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
