CREATE VIRTUAL TABLE IF NOT EXISTS idea_fts USING fts5(
  text,
  tags,
  source_ref,
  content='ideas',
  content_rowid='rowid',
  tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS ideas_ai AFTER INSERT ON ideas BEGIN
  INSERT INTO idea_fts(rowid, text, tags, source_ref)
  VALUES (new.rowid, new.text, new.tags, new.source_ref);
END;

CREATE TRIGGER IF NOT EXISTS ideas_ad BEFORE DELETE ON ideas BEGIN
  INSERT INTO idea_fts(idea_fts, rowid, text, tags, source_ref)
  VALUES ('delete', old.rowid, old.text, old.tags, old.source_ref);
END;

CREATE TRIGGER IF NOT EXISTS ideas_au AFTER UPDATE ON ideas BEGIN
  INSERT INTO idea_fts(idea_fts, rowid, text, tags, source_ref)
  VALUES ('delete', old.rowid, old.text, old.tags, old.source_ref);
  INSERT INTO idea_fts(rowid, text, tags, source_ref)
  VALUES (new.rowid, new.text, new.tags, new.source_ref);
END;

INSERT INTO idea_fts(idea_fts) VALUES ('rebuild');
