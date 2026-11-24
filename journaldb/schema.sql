PRAGMA foreign_keys=ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sources (
 source_id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL,
 system TEXT NOT NULL, edition TEXT NOT NULL, metric_year INTEGER,
 row_count INTEGER NOT NULL DEFAULT 0, duplicate_of TEXT REFERENCES sources(source_id),
 note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE journals (journal_id TEXT PRIMARY KEY, title TEXT NOT NULL, normalized_title TEXT NOT NULL);
CREATE TABLE identifiers (
 journal_id TEXT NOT NULL REFERENCES journals(journal_id), issn TEXT NOT NULL,
 PRIMARY KEY(journal_id,issn)
);
CREATE INDEX idx_identifiers_issn ON identifiers(issn);
CREATE TABLE aliases (
 journal_id TEXT NOT NULL REFERENCES journals(journal_id), title TEXT NOT NULL,
 normalized_title TEXT NOT NULL, PRIMARY KEY(journal_id,title)
);
CREATE INDEX idx_aliases_title ON aliases(normalized_title);
CREATE TABLE observations (
 observation_id INTEGER PRIMARY KEY, journal_id TEXT NOT NULL REFERENCES journals(journal_id),
 source_id TEXT NOT NULL REFERENCES sources(source_id), source_sheet TEXT,
 source_row INTEGER NOT NULL, title TEXT NOT NULL, match_method TEXT NOT NULL,
 metrics TEXT NOT NULL CHECK(json_valid(metrics)), raw TEXT NOT NULL CHECK(json_valid(raw)),
 quality_flags TEXT NOT NULL CHECK(json_valid(quality_flags)),
 UNIQUE(source_id,source_sheet,source_row)
);
CREATE INDEX idx_observations_journal ON observations(journal_id);
CREATE INDEX idx_observations_source ON observations(source_id);
CREATE TABLE catalogue (
 journal_id TEXT PRIMARY KEY REFERENCES journals(journal_id), title TEXT NOT NULL,
 issns TEXT NOT NULL, abdc TEXT, abdc_year INTEGER, ajg TEXT, ajg_year INTEGER,
 cas_zone INTEGER, cas_top INTEGER, cas_year INTEGER, impact_factor REAL,
 jcr_quartile TEXT, jcr_year INTEGER, sjr REAL, sjr_quartile TEXT, sjr_year INTEGER,
 ft50 INTEGER NOT NULL, utd24 INTEGER NOT NULL, publisher TEXT, country TEXT,
 source_type TEXT, wos_indexes TEXT NOT NULL, languages TEXT NOT NULL,
 taxonomy_paths TEXT NOT NULL CHECK(json_valid(taxonomy_paths)),
 subjects TEXT NOT NULL, search_text TEXT NOT NULL,
 quality_flags TEXT NOT NULL
);
CREATE INDEX idx_catalogue_abdc ON catalogue(abdc);
CREATE INDEX idx_catalogue_ajg ON catalogue(ajg);
CREATE INDEX idx_catalogue_cas ON catalogue(cas_zone);
CREATE INDEX idx_catalogue_if ON catalogue(impact_factor);
CREATE INDEX idx_catalogue_sjr ON catalogue(sjr);
CREATE INDEX idx_catalogue_ft ON catalogue(ft50,utd24);
CREATE VIEW journal_overview AS SELECT * FROM catalogue;
