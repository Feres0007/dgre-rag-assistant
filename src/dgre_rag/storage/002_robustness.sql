-- Additive schema: old immutable releases remain readable.
PRAGMA user_version = 2;
CREATE INDEX idx_evidence_source ON observation_evidence(source_id);
CREATE TABLE entity_assertions (
 assertion_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities,
 attribute TEXT NOT NULL, raw_value TEXT NOT NULL, normalized_value TEXT,
 unit TEXT, source_id TEXT NOT NULL REFERENCES sources,
 status TEXT NOT NULL CHECK(status IN ('candidate','validated','conflict'))
);
CREATE TABLE structured_records (
 record_id TEXT PRIMARY KEY, family TEXT NOT NULL, payload_json TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES sources, quality_status TEXT NOT NULL,
 extraction_method TEXT NOT NULL
);
CREATE INDEX idx_records_family ON structured_records(family);
CREATE TABLE source_links (
 source_id TEXT NOT NULL REFERENCES sources, related_id TEXT NOT NULL REFERENCES sources,
 relation TEXT NOT NULL, PRIMARY KEY(source_id,related_id,relation)
);
CREATE TABLE availability (
 availability_id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities,
 family TEXT NOT NULL, period_start TEXT, period_end TEXT,
 status TEXT NOT NULL, detail TEXT NOT NULL, source_id TEXT REFERENCES sources
);
CREATE TABLE figure_annotations (
 source_id TEXT PRIMARY KEY REFERENCES sources, caption TEXT NOT NULL,
 description TEXT, status TEXT NOT NULL DEFAULT 'unreviewed',
 numeric_evidence_json TEXT NOT NULL DEFAULT '[]'
);
