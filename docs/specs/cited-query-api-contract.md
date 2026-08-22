# Spec: v0.2.0 cited query API contract

## Status

Accepted and implemented foundation contract for the v0.2.0 cited-query slice. Phase 7 adds
SDK-free model-provider adapter boundaries, but the public `dev`/`serve` query surface remains the
same: default disabled unless an in-process harness explicitly installs capabilities, enables them,
and injects a provider.

## Objective

Define `POST /v1/query` precisely enough for implementation and tests to agree on request validation, capability gating, retrieval behavior, answer shape, citation shape, and provenance expectations.

The endpoint answers natural-language questions from stored ideas only. Any response that presents grounded claims based on stored ideas must include citations that resolve to persisted `Idea` records. If retrieval finds no relevant stored ideas, the endpoint returns an explicit no-evidence response with empty citations instead of inventing an answer.

## Scope

In scope for v0.2.0 foundation:

- HTTP contract for `POST /v1/query`.
- Deterministic/local/mock query service behavior.
- SQLite FTS-backed retrieval through the existing search contract.
- Citation records that point to persisted ideas and snippets/quotes.
- Capability-disabled behavior when `query-ai` or required dependencies are not enabled.
- Provenance expectations from raw event to draft to canonical idea where citation lineage is relevant.

Out of scope for this foundation:

- Public CLI/`.env` enablement for hosted or local model-provider adapters.
- Embeddings, vector search, hybrid ranking, reranking, or streaming answers.
- External connector runtimes beyond already persisted ideas.
- Browser/mobile UI, conversational sessions, public exposure, or production auth.
- Multi-user ownership, sharing, RBAC, or tenant-aware citation visibility.
- Returning raw event payload bodies from query responses.

## Capability gate

`POST /v1/query` is guarded by the `query-ai` capability. The route must not perform retrieval, provider calls, outbound network calls, or hidden startup work unless the capability registry reports the query capability as enabled and valid for the current process.

Minimum dependency expectations:

- `query-ai` depends on `core` and an enabled search capability such as `sqlite-fts-search`.
- The v0.2.0 foundation uses a deterministic built-in/mock answerer when explicitly enabled by tests or an embedded local harness.
- Real model providers remain disabled/unavailable until later provider-adapter work deliberately installs and enables them.
- If `query-ai` is disabled, unavailable, or misconfigured, the route returns a typed capability-disabled error instead of a no-evidence answer.

Capability-disabled response:

```text
503 Service Unavailable
```

```json
{
  "error": {
    "code": "CAPABILITY_DISABLED",
    "message": "Cited query is not enabled for this Idea Inbox instance.",
    "details": {
      "capability": "query-ai",
      "status": "disabled",
      "reason": "Enable and configure the query-ai capability before using POST /v1/query."
    }
  }
}
```

`details.status` should use capability registry vocabulary when available: `disabled`, `misconfigured`, or `unavailable`. Error details must not expose secret values or raw provider configuration.


## Current enablement surface

The public CLI server path constructs `create_app()` with the default `CapabilityRegistry()`, so
`query-ai` remains disabled even if `.env` contains `IDEA_INBOX_CHAT_PROVIDER=mock`. Current
enablement is intentionally limited to in-process tests or embedded harnesses that pass a custom
registry to `create_app(capability_registry=...)` with:

- installed provider capability metadata from `idea_inbox.providers.capabilities.provider_capabilities()`,
- `enabled_overrides` for `query-ai`, `model-provider`, the selected provider capability, and its
  credential-provider capability, and
- `config_values={"IDEA_INBOX_CHAT_PROVIDER": "mock"}`.

Disabling query means using the default registry, omitting the override, or explicitly passing
`enabled_overrides={"query-ai": False}`. A public CLI flag, config-file setting, environment-only
toggle, provider package discovery, and automatic provider construction from environment are later
work. The Phase 7 OpenAI-compatible and Ollama adapters are implemented request-mapping boundaries
for explicit harnesses; normal tests fake their HTTP boundary and do not call hosted APIs or local
model daemons.

## Request contract

```text
POST /v1/query
Content-Type: application/json
```

Request body:

```json
{
  "query": "What ideas did I save about local AI?",
  "limit": 10,
  "filters": {
    "source": "manual"
  },
  "include_hits": true
}
```

Fields:

| Field | Required | Shape | Rules |
| --- | --- | --- | --- |
| `query` | yes | string | Trimmed. Must be non-empty after trimming. Maximum length: 2,000 characters. |
| `limit` | no | integer | Defaults to `10`. Must be from `1` through `50`, matching the current FTS search limit contract. |
| `filters` | no | object | Optional deterministic retrieval filters. v0.2.0 foundation only accepts `source` as a non-empty string when present. Unknown filter keys return validation errors until specified. |
| `include_hits` | no | boolean | Defaults to `true`. When `false`, response `hits` may be an empty list even when citations exist; citations remain required for grounded claims. |

Validation failures use the standard error envelope:

```text
400 Bad Request
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Query must not be empty.",
    "details": { "field": "query" }
  }
}
```

Provider-boundary failures after request validation and retrieval, such as missing adapter credentials
or malformed hosted/local model responses, use a provider error instead of the validation envelope:

```text
502 Bad Gateway
```

```json
{
  "error": {
    "code": "PROVIDER_ERROR",
    "message": "Query provider could not answer the request.",
    "details": { "provider": "mock" }
  }
}
```

Provider error details may include a non-secret provider name, but must not expose credentials,
raw provider payloads, or SDK exception text.

## Success response with evidence

A successful evidence-backed answer returns `200 OK`.

```json
{
  "answer": {
    "message": "You saved an idea to prototype local-first capture before connector work.",
    "grounding": "stored_ideas"
  },
  "citations": [
    {
      "citation_id": "c1",
      "idea_id": "idea_01HZY...",
      "snippet": "Prototype local-first capture before connector work.",
      "source": "manual",
      "source_ref": "note-1",
      "captured_at": "2026-08-09T00:00:00Z",
      "provenance": {
        "raw_event_id": "raw_01HZY...",
        "draft_id": "draft_01HZY..."
      }
    }
  ],
  "hits": [
    {
      "idea_id": "idea_01HZY...",
      "rank": 1,
      "score": -1.23,
      "snippet": "Prototype <mark>local</mark>-first capture before connector work.",
      "source": "manual",
      "captured_at": "2026-08-09T00:00:00Z"
    }
  ],
  "meta": {
    "query": "What ideas did I save about local AI?",
    "limit": 10,
    "grounding": "stored_ideas",
    "answer_mode": "deterministic_mock",
    "model_provider": "mock",
    "retrieval": { "strategy": "sqlite_fts", "evidence_count": 1 }
  }
}
```

Response fields:

| Field | Shape | Rules |
| --- | --- | --- |
| `answer.message` | string | Human-readable answer. Every grounded claim based on stored ideas must be supported by at least one citation in `citations`. |
| `answer.grounding` | enum string | `stored_ideas` for evidence-backed answers. |
| `citations` | list | Required. Non-empty for `stored_ideas` answers. Each citation must resolve to a persisted idea. |
| `hits` | list | Retrieval diagnostics shaped like search hits. Included by default for deterministic tests and debugging; may be empty only when `include_hits=false` or no evidence exists. |
| `meta` | object | Safe non-secret execution metadata for tests/debugging. |

## No-evidence response

When retrieval runs successfully but finds no relevant stored ideas, return `200 OK` with an explicit no-evidence message and empty citation arrays.

```json
{
  "answer": {
    "message": "I could not find relevant stored ideas for that query.",
    "grounding": "no_relevant_stored_ideas"
  },
  "citations": [],
  "hits": [],
  "meta": {
    "query": "What did I save about Mars colony budgets?",
    "limit": 10,
    "grounding": "no_relevant_stored_ideas",
    "answer_mode": "deterministic_mock",
    "retrieval": { "strategy": "sqlite_fts", "evidence_count": 0 }
  }
}
```

Required behavior:

- Do not call a real model provider for no-evidence generation in the v0.2.0 foundation.
- Do not generate grounded claims from general model knowledge or project assumptions.
- Use exactly the semantic grounding value `no_relevant_stored_ideas` for this case.
- Keep `citations` empty.
- Keep `hits` empty.

## Citation contract

Each citation is evidence, not decoration. A citation must reference a stored idea record, and answer generation must not cite only a search-index row, model-generated reference, or raw event that has no persisted derived idea.

Citation fields:

| Field | Required | Shape | Meaning |
| --- | --- | --- | --- |
| `citation_id` | yes | string | Stable within one response, usually `c1`, `c2`, etc. |
| `idea_id` | yes | string | Persisted `Idea.id` used as answer evidence. |
| `snippet` | yes | string | Quote/snippet from the persisted idea text. It may be the FTS snippet or a deterministic quote window, but it must come from the stored idea text. |
| `source` | yes | string | `Idea.source`, for example `manual`. |
| `source_ref` | yes | string or null | `Idea.source_ref` when available. |
| `captured_at` | yes | string | `Idea.captured_at`. |
| `provenance.raw_event_id` | when available | string | The raw event from which the cited idea was derived. Required when the storage record has it. |
| `provenance.draft_id` | when available | string | The draft from which the cited idea was derived. Required when the storage record has it. |

A query response may cite multiple snippets from the same idea, but the first foundation implementation should prefer one citation per idea unless tests require otherwise. Citation order follows the evidence order used for answer generation.

## Provenance requirements

The query path must preserve the existing ingestion lineage:

```text
RawEvent -> IdeaDraft -> Idea -> SearchHit -> Citation
```

Rules:

1. Retrieval may start from `SearchHit` values returned by a search projection.
2. Before building citations or grounded answer evidence, the service must resolve each hit through authoritative storage by `idea_id`.
3. The answerer receives only the user query and resolved evidence records/snippets selected from stored ideas.
4. Citations must expose `idea_id` and safe source metadata. They should expose raw-event and draft identifiers when those are present on storage records, but they must not return raw event payload bodies by default.
5. If a search hit cannot be resolved to a non-deleted persisted idea, it is dropped from evidence. If all hits are dropped, return the no-evidence response.
6. Generated or deterministic answers must never invent `idea_id`, `raw_event_id`, source metadata, snippets, or quote text.

## Grounding and fabrication rules

Implementation and tests should enforce these invariants:

- `answer.grounding == "stored_ideas"` requires `citations` to be non-empty.
- Any claim about what the user stored, saved, captured, planned, or decided is a grounded claim and requires a citation.
- `answer.grounding == "no_relevant_stored_ideas"` requires `citations == []` and must use the explicit no-relevant-stored-ideas message.
- The service may return ungrounded operational text only for validation/capability errors or no-evidence messaging; it must not mix uncited stored-idea claims into those messages.
- If deterministic/mock answer construction cannot support a claim from resolved evidence, omit the claim rather than adding an uncited sentence.

## Deterministic/mock foundation behavior

The implemented v0.2.0 foundation is testable without real model calls:

1. Validate the request.
2. Check the `query-ai` capability gate.
3. Run the configured deterministic search path with `query`, `limit`, and accepted filters.
4. Resolve hits to persisted ideas and safe provenance identifiers.
5. If no resolved evidence exists, return the no-evidence response.
6. Otherwise build a deterministic answer from resolved snippets/idea text and return citations.

Normal tests must not call hosted models, local model daemons, connector APIs, embedding providers, or external networks.

## Test-driving checklist

Implementation tests cover or should continue covering:

- `POST /v1/query` returns `CAPABILITY_DISABLED` when `query-ai` is disabled, unavailable, or misconfigured.
- Request validation rejects non-object bodies, blank `query`, too-long `query`, invalid `limit`, invalid filters, and unknown filter keys.
- Provider-boundary failures return `PROVIDER_ERROR` and are not reported as request validation or limit errors.
- Evidence-backed responses include `answer.grounding == "stored_ideas"`, at least one citation, and citation `idea_id` values that exist in storage.
- Search hits are resolved through storage before citation creation.
- Missing/deleted ideas referenced by stale search hits are not cited.
- No-evidence retrieval returns `answer.grounding == "no_relevant_stored_ideas"`, the explicit message, empty citations, and empty hits.
- Deterministic/mock answering never emits stored-idea claims without citations.
- Raw event payload bodies are not returned by default, while raw-event/draft IDs are preserved in `citation.provenance` where available.

## Non-goals and future extensions

Future specs may add public provider enablement, automatic provider construction, embeddings/hybrid
search, streaming, auth, UI, richer provider selection, source/date filters, citations with
byte/character offsets, or public exposure hardening. Those additions must remain additive to this
foundation contract and must not relax the citation/fabrication invariants above.
