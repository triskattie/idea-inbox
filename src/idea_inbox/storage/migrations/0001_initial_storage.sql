CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
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
  UNIQUE (source, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_raw_events_source_dedupe
  ON raw_events(source, dedupe_key);

CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY,
  raw_event_id TEXT NOT NULL REFERENCES raw_events(id),
  text TEXT NOT NULL,
  source TEXT NOT NULL,
  source_ref TEXT,
  captured_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  tags TEXT NOT NULL DEFAULT '',
  embedding_state TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ideas_raw_event_id ON ideas(raw_event_id);
CREATE INDEX IF NOT EXISTS idx_ideas_source ON ideas(source);
CREATE INDEX IF NOT EXISTS idx_ideas_captured_at ON ideas(captured_at);
