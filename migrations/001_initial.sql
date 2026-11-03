CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY);
CREATE TABLE IF NOT EXISTS owner_sessions (
 id text PRIMARY KEY, token_hash text UNIQUE NOT NULL, csrf_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS videos (
 id text PRIMARY KEY, owner_id text NOT NULL REFERENCES owner_sessions(id),
 sha256 text NOT NULL, metadata jsonb NOT NULL, features jsonb,
 created_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
 fence integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS runs (
 id text PRIMARY KEY, video_id text NOT NULL REFERENCES videos(id),
 status text NOT NULL DEFAULT 'queued', stage text NOT NULL DEFAULT 'queued',
 sequence integer NOT NULL DEFAULT 0, error_code text, report jsonb,
 created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS jobs (
 id text PRIMARY KEY, video_id text NOT NULL REFERENCES videos(id), run_id text REFERENCES runs(id) ON DELETE CASCADE,
 kind text NOT NULL CHECK (kind IN ('analysis','deletion')), status text NOT NULL DEFAULT 'queued',
 generation integer NOT NULL DEFAULT 0, lease_until timestamptz, available_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs (status, available_at, lease_until);
CREATE TABLE IF NOT EXISTS checkpoints (
 run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE, persona_id text NOT NULL,
 next_scene integer NOT NULL DEFAULT 0, status text NOT NULL DEFAULT 'active', impression text NOT NULL DEFAULT '',
 PRIMARY KEY (run_id,persona_id)
);
CREATE TABLE IF NOT EXISTS reactions (
 run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE, persona_id text NOT NULL, scene_id integer NOT NULL,
 reaction jsonb NOT NULL, evidence jsonb NOT NULL, PRIMARY KEY(run_id,persona_id,scene_id)
);
CREATE TABLE IF NOT EXISTS events (
 run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE, sequence integer NOT NULL,
 event_id text UNIQUE NOT NULL, type text NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY (run_id,sequence)
);
CREATE TABLE IF NOT EXISTS provider_calls (
 run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE, unit text NOT NULL,
 status text NOT NULL, audit jsonb NOT NULL, receipt jsonb, PRIMARY KEY(run_id,unit)
);
CREATE TABLE IF NOT EXISTS objects (
 key text PRIMARY KEY, video_id text NOT NULL REFERENCES videos(id), kind text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS deletions (
 id text PRIMARY KEY, video_id text UNIQUE NOT NULL REFERENCES videos(id),
 owner_id text NOT NULL REFERENCES owner_sessions(id), state jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
 owner_id text NOT NULL REFERENCES owner_sessions(id), route text NOT NULL, key text NOT NULL,
 body_hash text NOT NULL, result jsonb NOT NULL, PRIMARY KEY(owner_id,route,key)
);
INSERT INTO schema_migrations VALUES(1) ON CONFLICT DO NOTHING;
