-- Additive V03 run configuration. Existing V02 runs keep their three-person profile.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS manifest jsonb NOT NULL DEFAULT
'{"schema_version":"run-manifest-1","profile":"test","provider_mode":"recorded","requested":3,"persona_ids":["p001","p002","p003"],"resample_seed":20261028}'::jsonb;

DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='runs_manifest_shape' AND conrelid='runs'::regclass) THEN
  ALTER TABLE runs ADD CONSTRAINT runs_manifest_shape CHECK (
   manifest ?& ARRAY['schema_version','profile','provider_mode','requested','persona_ids','resample_seed']
   AND manifest->>'schema_version'='run-manifest-1'
   AND manifest->>'profile' IN ('test','flash')
   AND manifest->>'provider_mode' IN ('recorded','standard')
   AND (manifest->>'requested')::integer = CASE manifest->>'profile' WHEN 'test' THEN 3 ELSE 50 END
   AND jsonb_typeof(manifest->'persona_ids')='array'
   AND jsonb_array_length(manifest->'persona_ids')=(manifest->>'requested')::integer
   AND (manifest->>'resample_seed')::bigint >= 0
  );
 END IF;
END $$;

CREATE OR REPLACE FUNCTION protect_run_manifest() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE total integer; unique_total integer;
BEGIN
 IF TG_OP='UPDATE' AND NEW.manifest IS DISTINCT FROM OLD.manifest THEN
  RAISE EXCEPTION 'run_manifest_immutable' USING ERRCODE='23514';
 END IF;
 SELECT count(*),count(DISTINCT value) INTO total,unique_total
 FROM jsonb_array_elements_text(NEW.manifest->'persona_ids');
 IF total <> unique_total OR EXISTS (
  SELECT 1 FROM jsonb_array_elements(NEW.manifest->'persona_ids') p WHERE jsonb_typeof(p)<>'string'
 ) THEN
  RAISE EXCEPTION 'run_manifest_persona_ids_invalid' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS runs_manifest_guard ON runs;
CREATE TRIGGER runs_manifest_guard BEFORE INSERT OR UPDATE OF manifest ON runs
FOR EACH ROW EXECUTE FUNCTION protect_run_manifest();
INSERT INTO schema_migrations VALUES(2) ON CONFLICT DO NOTHING;
