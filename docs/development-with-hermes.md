# Development with Hermes Agent

Idea Inbox has been mainly coded using Hermes Agent, with Tris acting as the human supervisor, creative director, product owner, reviewer, and final decision-maker.

This is intentional project history, not a claim that the software is autonomous or unaudited. Hermes Agent helps with implementation and verification, while the human role sets direction, decides what is worth building, approves scope, and catches taste/product issues that automation cannot own.

## Collaboration model

- **Human supervisor:** chooses goals, release standards, and whether the current result is good enough.
- **Creative director:** shapes the product feel, contributor posture, and what a usable first release should mean.
- **Hermes Agent:** drafts plans, edits code and docs, runs commands, verifies tests, and reports concrete tool output.
- **Git history:** records the actual implementation slices through conventional commits.

## Hermes Agent features used

This project has used these Hermes Agent capabilities during early development:

- **planning:** written implementation/release plans before coding larger slices.
- **skills:** reusable workflows for plan-first development, TDD, GitHub/release work, API design, and documentation.
- **tool-based verification:** real `uv`, `ruff`, `pytest`, `git`, and CLI commands are run before claims are made.
- **Repository inspection:** file reads, searches, git status checks, and spec lookups keep changes grounded in repo evidence.
- **Patch-based editing:** targeted file edits instead of manual copy/paste rewrites.
- **Persistent project context:** stable project goals and workflow preferences are remembered across sessions.
- **Human-in-the-loop review:** Hermes can implement and verify, but release decisions and product direction stay supervised.

## Development standard

AI assistance does not lower the bar for this repository. Changes still need:

- a written spec or accepted plan for behavior changes,
- test-first implementation where behavior changes,
- passing local verification,
- clear documentation when user-facing behavior changes,
- human review before important release decisions.

The intended tone is transparent: this is a human-directed, AI-assisted open source project.