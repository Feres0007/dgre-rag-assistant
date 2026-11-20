-- Socle à compléter par les validations applicatives du guide.
PRAGMA foreign_keys = ON;
CREATE TABLE documents (
 document_id TEXT PRIMARY KEY,
 original_name TEXT NOT NULL,
 sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256)=64),
 page_count INTEGER NOT NULL CHECK(page_count>0),
 edition TEXT NOT NULL
);
CREATE TABLE sources (
 source_id TEXT PRIMARY KEY,
 document_id TEXT NOT NULL REFERENCES documents(document_id),
 page_pdf INTEGER NOT NULL CHECK(page_pdf>=1),
 page_printed TEXT,
 parent_id TEXT REFERENCES sources(source_id),
 kind TEXT NOT NULL,
 x0 REAL NOT NULL, y0 REAL NOT NULL, x1 REAL NOT NULL, y1 REAL NOT NULL,
 raw_text TEXT NOT NULL,
 CHECK(x1>x0 AND y1>y0)
);
CREATE TABLE cells (
 cell_id TEXT PRIMARY KEY,
 source_id TEXT NOT NULL REFERENCES sources(source_id),
 row_index INTEGER NOT NULL CHECK(row_index>=0),
 col_index INTEGER NOT NULL CHECK(col_index>=0),
 headers_json TEXT NOT NULL,
 raw_value TEXT NOT NULL,
 normalized_value TEXT,
 symbol_status TEXT NOT NULL,
 UNIQUE(source_id,row_index,col_index)
);
CREATE TABLE entities (
 entity_id TEXT PRIMARY KEY,
 kind TEXT NOT NULL,
 canonical_name TEXT NOT NULL
);
CREATE TABLE entity_mentions (
 mention_id TEXT PRIMARY KEY,
 entity_id TEXT REFERENCES entities(entity_id),
 source_id TEXT NOT NULL REFERENCES sources(source_id),
 source_code TEXT,
 source_name TEXT NOT NULL,
 resolution_status TEXT NOT NULL
);
CREATE TABLE entity_relations (
 relation_id TEXT PRIMARY KEY,
 from_entity TEXT NOT NULL REFERENCES entities(entity_id),
 to_entity TEXT NOT NULL REFERENCES entities(entity_id),
 relation_type TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES sources(source_id)
);
CREATE TABLE metrics (
 metric_id TEXT PRIMARY KEY,
 definition TEXT NOT NULL,
 canonical_unit TEXT NOT NULL,
 temporal_kind TEXT NOT NULL,
 allowed_operations_json TEXT NOT NULL
);
CREATE TABLE baselines (
 baseline_id TEXT PRIMARY KEY,
 label TEXT NOT NULL,
 period_start TEXT,
 period_end TEXT,
 number_of_years INTEGER,
 method TEXT,
 source_id TEXT NOT NULL REFERENCES sources(source_id)
);
CREATE TABLE observations (
 observation_id TEXT PRIMARY KEY,
 entity_id TEXT NOT NULL REFERENCES entities(entity_id),
 metric_id TEXT NOT NULL REFERENCES metrics(metric_id),
 period_start TEXT,
 period_end TEXT,
 event_date TEXT,
 event_time TEXT,
 value_decimal TEXT,
 unit TEXT NOT NULL,
 precision_decimal TEXT,
 baseline_id TEXT REFERENCES baselines(baseline_id),
 value_status TEXT NOT NULL,
 quality_status TEXT NOT NULL CHECK(quality_status IN ('candidate','validated','blocked')),
 origin TEXT NOT NULL CHECK(origin IN ('published','calculated')),
 validation_method TEXT,
 CHECK(period_start IS NULL OR period_end IS NULL OR period_start<=period_end)
);
CREATE TABLE observation_evidence (
 observation_id TEXT NOT NULL REFERENCES observations(observation_id),
 source_id TEXT NOT NULL REFERENCES sources(source_id),
 cell_id TEXT REFERENCES cells(cell_id),
 role TEXT NOT NULL,
 PRIMARY KEY(observation_id,source_id,role)
);
CREATE TABLE derivations (
 output_id TEXT PRIMARY KEY REFERENCES observations(observation_id),
 formula_id TEXT NOT NULL,
 formula_version TEXT NOT NULL,
 parameters_json TEXT NOT NULL,
 coverage_json TEXT NOT NULL
);
CREATE TABLE derivation_inputs (
 output_id TEXT NOT NULL REFERENCES derivations(output_id),
 input_id TEXT NOT NULL REFERENCES observations(observation_id),
 role TEXT NOT NULL,
 PRIMARY KEY(output_id,input_id,role),
 CHECK(output_id<>input_id)
);
CREATE TABLE quality_issues (
 issue_id TEXT PRIMARY KEY,
 source_id TEXT REFERENCES sources(source_id),
 observation_id TEXT REFERENCES observations(observation_id),
 code TEXT NOT NULL,
 severity TEXT NOT NULL,
 status TEXT NOT NULL,
 detail TEXT NOT NULL,
 resolution TEXT
);
CREATE TABLE observation_selections (
 selection_key TEXT PRIMARY KEY,
 observation_id TEXT NOT NULL REFERENCES observations(observation_id),
 policy_version TEXT NOT NULL,
 justification TEXT NOT NULL
);
CREATE TABLE coverage (
 coverage_id TEXT PRIMARY KEY,
 entity_id TEXT REFERENCES entities(entity_id),
 metric_id TEXT NOT NULL REFERENCES metrics(metric_id),
 period_start TEXT NOT NULL,
 period_end TEXT NOT NULL,
 granularity TEXT NOT NULL,
 expected_count INTEGER,
 available_count INTEGER NOT NULL CHECK(available_count>=0),
 valid_count INTEGER NOT NULL CHECK(valid_count>=0),
 unresolved_count INTEGER NOT NULL CHECK(unresolved_count>=0),
 counting_method TEXT NOT NULL,
 CHECK(valid_count<=available_count)
);
CREATE TABLE chunks (
 chunk_id TEXT PRIMARY KEY,
 source_id TEXT NOT NULL REFERENCES sources(source_id),
 parent_chunk_id TEXT REFERENCES chunks(chunk_id),
 text TEXT NOT NULL,
 metadata_json TEXT NOT NULL
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, text);
CREATE INDEX idx_observations_lookup ON observations(entity_id,metric_id,period_start,period_end);
CREATE INDEX idx_sources_location ON sources(document_id,page_pdf);
