-- 0001_postgres_foundation: mirrors the SQLite foundation schema.
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
    processing_state TEXT NOT NULL DEFAULT 'pending',
    error_code TEXT,
    error_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT raw_events_source_dedupe_unique UNIQUE (source, dedupe_key)
);

CREATE TABLE IF NOT EXISTS idea_drafts (
    id TEXT PRIMARY KEY,
    raw_event_id TEXT NOT NULL REFERENCES raw_events(id),
    text TEXT NOT NULL,
    source_created_at TEXT,
    source_uri TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    extraction_state TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags TEXT NOT NULL DEFAULT '',
    embedding_state TEXT NOT NULL DEFAULT 'not_requested',
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS idea_tags (
    idea_id TEXT NOT NULL REFERENCES ideas(id),
    tag TEXT NOT NULL,
    UNIQUE (idea_id, tag)
);

CREATE INDEX IF NOT EXISTS ideas_raw_event_id_idx ON ideas (raw_event_id);
CREATE INDEX IF NOT EXISTS idea_drafts_raw_event_id_idx ON idea_drafts (raw_event_id);
CREATE INDEX IF NOT EXISTS idea_tags_tag_idx ON idea_tags (tag);

-- Keyword-search projection over canonical ideas using tsvector.
-- The pgvector extension remains available in the deployment image for a later
-- embeddings/hybrid search phase; this profile does not create vector columns yet.
CREATE OR REPLACE FUNCTION ideas_search_document() RETURNS trigger AS $$
BEGIN
    INSERT INTO idea_search (idea_id, document)
    VALUES (NEW.id, to_tsvector('simple', NEW.text || ' ' || NEW.tags || ' ' || COALESCE(NEW.source_ref, '')))
    ON CONFLICT (idea_id) DO UPDATE
        SET document = EXCLUDED.document;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS idea_search (
    idea_id TEXT PRIMARY KEY REFERENCES ideas(id) ON DELETE CASCADE,
    document TSVECTOR NOT NULL
);

DROP TRIGGER IF EXISTS idea_search_upsert_trigger ON ideas;
CREATE TRIGGER idea_search_upsert_trigger
AFTER INSERT OR UPDATE OF text, tags, source_ref ON ideas
FOR EACH ROW EXECUTE FUNCTION ideas_search_document();

INSERT INTO idea_search (idea_id, document)
SELECT id, to_tsvector('simple', text || ' ' || tags || ' ' || COALESCE(source_ref, ''))
FROM ideas
ON CONFLICT (idea_id) DO NOTHING;
