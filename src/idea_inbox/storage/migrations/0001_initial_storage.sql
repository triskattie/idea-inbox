CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_events (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  provider_event_id TEXT,
  dedupe_key TEXT NOT NULL,
  received_at TEXT NOT NULL,
  occurred_at TEXT,
  actor_ref TEXT,
  payload TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  processing_state TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (source, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_raw_events_source_dedupe
  ON raw_events(source, dedupe_key);
CREATE INDEX IF NOT EXISTS idx_raw_events_source_provider_event_id
  ON raw_events(source, provider_event_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_processing_state ON raw_events(processing_state);
CREATE INDEX IF NOT EXISTS idx_raw_events_received_at ON raw_events(received_at);

CREATE TABLE IF NOT EXISTS idea_drafts (
  id TEXT PRIMARY KEY,
  raw_event_id TEXT NOT NULL REFERENCES raw_events(id),
  text TEXT NOT NULL,
  source_created_at TEXT,
  source_uri TEXT,
  metadata TEXT NOT NULL DEFAULT '{}',
  extraction_state TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_idea_drafts_raw_event_id ON idea_drafts(raw_event_id);
CREATE INDEX IF NOT EXISTS idx_idea_drafts_extraction_state ON idea_drafts(extraction_state);

CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY,
  raw_event_id TEXT NOT NULL REFERENCES raw_events(id),
  draft_id TEXT REFERENCES idea_drafts(id),
  text TEXT NOT NULL,
  source TEXT NOT NULL,
  source_ref TEXT,
  captured_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  tags TEXT NOT NULL DEFAULT '',
  embedding_state TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ideas_raw_event_id ON ideas(raw_event_id);
CREATE INDEX IF NOT EXISTS idx_ideas_draft_id ON ideas(draft_id);
CREATE INDEX IF NOT EXISTS idx_ideas_source_ref ON ideas(source, source_ref);
CREATE INDEX IF NOT EXISTS idx_ideas_captured_at ON ideas(captured_at);
CREATE INDEX IF NOT EXISTS idx_ideas_embedding_state ON ideas(embedding_state);

CREATE TABLE IF NOT EXISTS idea_tags (
  idea_id TEXT NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (idea_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_idea_tags_tag ON idea_tags(tag);
