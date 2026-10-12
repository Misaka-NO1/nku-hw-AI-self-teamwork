-- Backward-compatible optional CATEGORY credit aggregates only. No course/grade/identity storage.
-- Run AFTER degree-agent-import-migration.sql. No tables, grants, owner or auth changes.
-- Guarded edits preserve the full deployed RPC authorization and confirmation body.
BEGIN;
DO $migration$
DECLARE target regprocedure; definition text; original text; error_return text;
 old_guard text := 'OR (SELECT count(*) FROM jsonb_object_keys(m))<>5';
 new_guard text := $guard$OR EXISTS(SELECT 1 FROM jsonb_object_keys(m) AS field(key)
    WHERE key NOT IN ('title','required_credits','school_actual_credits','school_status','school_note',
      'school_in_progress_credits','school_direct_in_progress_credits'))$guard$;
 marker text := 'FOR k IN SELECT unnest(ARRAY[''school_status'',''school_note'']) LOOP';
 validation text;
BEGIN
 FOREACH target IN ARRAY ARRAY[
  'nku_degree_progress_v1.valid_report(jsonb)'::regprocedure,
  'public.nku_degree_progress_v1_rpc(text,jsonb)'::regprocedure] LOOP
  definition := pg_get_functiondef(target); original := definition;
  IF definition LIKE '%school_direct_in_progress_credits%' THEN
   RAISE EXCEPTION 'In-progress validation already installed; do not replay migration';
  END IF;
  IF position(old_guard IN definition)=0 OR position(marker IN definition)=0 THEN
   RAISE EXCEPTION 'Unexpected degree validator version; nothing changed';
  END IF;
  error_return := CASE WHEN target='nku_degree_progress_v1.valid_report(jsonb)'::regprocedure
   THEN 'RETURN false;' ELSE 'RETURN nku_identity_pilot_v1.err(422,''VALIDATION_ERROR'');' END;
  validation := format($checks$
  FOR k IN SELECT unnest(ARRAY['school_in_progress_credits','school_direct_in_progress_credits']) LOOP
   IF m ? k AND m->k<>'null'::jsonb THEN
    IF jsonb_typeof(m->k) IS DISTINCT FROM 'string'
     OR coalesce(m->>k,'') !~ '^(0|[1-9][0-9]{0,2})(\.[0-9]{1,2})?$' THEN %s END IF;
    IF (m->>k)::numeric>300 OR (m->>k)::numeric>(m->>'school_actual_credits')::numeric THEN %s END IF;
   END IF;
  END LOOP;
  IF m->>'school_direct_in_progress_credits' IS NOT NULL AND
   (m->>'school_in_progress_credits' IS NULL OR
    (m->>'school_direct_in_progress_credits')::numeric>(m->>'school_in_progress_credits')::numeric)
   THEN %s END IF;
  $checks$,error_return,error_return,error_return);
  definition := replace(definition,old_guard,new_guard);
  definition := replace(definition,marker,validation||marker);
  IF definition=original THEN RAISE EXCEPTION 'No expected validator edit'; END IF;
  EXECUTE definition;
 END LOOP;
END $migration$;
COMMIT;
