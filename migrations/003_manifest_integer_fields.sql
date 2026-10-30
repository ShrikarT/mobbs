-- Tighten the already-applied V03 manifest guard without rewriting migration002
-- or changing any sealed manifest. Canonical V02/test and Flash values are integers.
DO $$ BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM pg_constraint
  WHERE conname='runs_manifest_integer_fields' AND conrelid='runs'::regclass
 ) THEN
  ALTER TABLE runs ADD CONSTRAINT runs_manifest_integer_fields CHECK ((
   jsonb_typeof(manifest->'requested')='number'
   AND manifest->>'requested' ~ '^(0|[1-9][0-9]*)$'
   AND jsonb_typeof(manifest->'resample_seed')='number'
   AND manifest->>'resample_seed' ~ '^(0|[1-9][0-9]*)$'
  ) IS TRUE);
 END IF;
END $$;
INSERT INTO schema_migrations VALUES(3) ON CONFLICT DO NOTHING;
