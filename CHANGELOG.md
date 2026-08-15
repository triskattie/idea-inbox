# Changelog

All notable changes to Idea Inbox will be documented here.

The format follows Keep a Changelog-style sections: Added, Changed, Deprecated, Removed, Fixed, Security.

## [Unreleased]

### Added

- Initial repository documentation and development standards.
- CLI parsing for smoke, `dev`, `migrate`, and `serve` commands, including implemented SQLite
  migration execution through `idea-inbox migrate` and runnable `dev`/`serve` WSGI API startup.
- SQLite configuration, deterministic migrations, durable raw event/draft/idea storage, and the
  rebuildable FTS5 search projection.
- WSGI API endpoints for manual capture and FTS-backed idea search.
- Manual idea capture through `POST /v1/ideas`, preserving a raw event before derived idea
  records and normalizing tags, metadata, and source fields.
