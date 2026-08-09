# Provider Guide

Providers supply model, embedding, and credential capabilities.

## Model providers

The core must not assume OpenAI API keys. Supported paths should include:

- mock provider for tests
- OpenAI-compatible HTTP provider
- Ollama/local provider
- local sentence-transformer embedding provider
- OAuth/proxy/Codex-style credential flows later

## Credential providers

Credential providers allow a model provider to request credentials without knowing where they came from.

Initial providers can be simple:

- `none`
- `env_api_key`
- `static_config`

Future providers:

- `oauth_device_code`
- `codex_login`
- `hermes_proxy`
- `browser_login`
