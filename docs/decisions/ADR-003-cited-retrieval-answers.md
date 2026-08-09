# ADR-003: Retrieval answers require citations

## Status
Accepted

## Context

The assistant must answer from the user's captured ideas, not invent project memory.

## Decision

Generated query answers must cite the ideas used as evidence. If no relevant ideas are found, the assistant must say so.

## Consequences

- Query quality is easier to debug.
- Users can trace answers back to source messages.
- Prompting and tests must enforce retrieval-only answer behavior.
