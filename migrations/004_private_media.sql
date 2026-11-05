CREATE TABLE IF NOT EXISTS media_objects (
 key text PRIMARY KEY REFERENCES objects(key) ON DELETE CASCADE,
 bytes bigint NOT NULL CHECK (bytes >= 0),
 content_type text NOT NULL
);
CREATE TABLE IF NOT EXISTS media_chunks (
 key text NOT NULL REFERENCES media_objects(key) ON DELETE CASCADE,
 part integer NOT NULL CHECK (part >= 0),
 data bytea NOT NULL,
 PRIMARY KEY(key,part)
);
INSERT INTO schema_migrations VALUES(4) ON CONFLICT DO NOTHING;
