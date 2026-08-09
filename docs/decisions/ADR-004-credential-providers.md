# ADR-004: Credential providers support API keys and OAuth-style flows

## Status
Accepted

## Context

Users may want local AI, OpenAI-compatible APIs, Hermes proxy, or Codex-style OAuth logins. Hardcoding static API keys would create a future rewrite. The MVP architecture spec requires hosted model use to be optional, providers to be configured explicitly, and normal tests to use deterministic mocks rather than real model calls.

See [`../specs/mvp-architecture-spec.md`](../specs/mvp-architecture-spec.md), especially the provider design, configuration surface, privacy/security assumptions, and future work sections.

## Decision

Model providers obtain secrets through a credential provider abstraction. MVP can ship `none`, env/static, and mock credential paths, but contracts must allow device login, OAuth refresh, browser/Codex-style login, local proxy providers, and fully local/no-secret model paths later.

Model providers own model API calls and provider-specific request/response mapping. Credential providers own secret lookup, refresh, persistence policy, and login/session lifecycle. Core domain contracts must not expose provider SDK credential objects.

## Consequences

- Provider config is slightly more explicit.
- Future non-API-key login paths can be added as new credential providers.
- Static API keys remain one supported credential source, not the architectural default or only supported path.
- Tests for provider contracts should cover at least one non-secret/mock credential provider so core behavior does not become API-key-only by accident.
