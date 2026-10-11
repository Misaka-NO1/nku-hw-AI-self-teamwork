-- Additive guard AFTER browser-visitor-migration.sql. Preserve all existing data.
-- A new browser is not a new account. Unknown browser proof cannot enroll.
BEGIN;
ALTER FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb)
 RENAME TO nku_identity_pilot_v1_before_identity_first_rpc;
CREATE FUNCTION public.nku_identity_pilot_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE owner text;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>900000 THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF op='visitor_probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','browser-visitor-identity-first-v2')); END IF;
 IF op='visitor_begin' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(args))<>6 OR NOT args ?& ARRAY[
   'challenge_hash','code_hash','subject_id','token_hash','csrf_hash','workspace_ref']
   OR jsonb_typeof(args->'challenge_hash') IS DISTINCT FROM 'string'
   OR coalesce(args->>'challenge_hash','') !~ '^[0-9a-f]{64}$' THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  -- Same lock as legacy enrollment/resume. Check and resume are one transaction.
  PERFORM pg_advisory_xact_lock(604022001);
  SELECT subject_id INTO owner FROM nku_identity_pilot_v1.browser_visitors
   WHERE challenge_hash=args->>'challenge_hash';
  IF owner IS NULL THEN
   IF EXISTS(SELECT 1 FROM nku_identity_pilot_v1.agent_devices
    WHERE challenge_hash=args->>'challenge_hash' AND owner_subject_id IS NOT NULL) THEN
    RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
  IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=owner) THEN
   RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 END IF;
 RETURN public.nku_identity_pilot_v1_before_identity_first_rpc(op,args);
END $$;
-- No public/service_role bypass of the previous enrollment function.
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_before_identity_first_rpc(text,jsonb)
 FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) TO service_role;
COMMIT;
