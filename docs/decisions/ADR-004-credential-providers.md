# ADR-004: Credential providers support API keys and OAuth-style flows

## Status
Accepted

## Context

Users may want local AI, OpenAI-compatible APIs, Hermes proxy, or Codex-style OAuth logins. Hardcoding static API keys would create a future rewrite.

## Decision

Model providers obtain secrets through a credential provider abstraction. MVP can ship env/static providers, but contracts must allow device login, OAuth refresh, and local proxy providers later.

## Consequences

- Provider config is slightly more explicit.
- Future non-API-key login paths can be added as new credential providers.
