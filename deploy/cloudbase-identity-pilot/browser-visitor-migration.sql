-- Additive private visitor spaces. Run AFTER agent-device-binding and task-delete.
-- No school identity assertion, registered-user expansion, public DB access or data migration.
BEGIN;
CREATE TABLE nku_identity_pilot_v1.browser_visitors (
 challenge_hash text PRIMARY KEY CHECK(challenge_hash ~ '^[0-9a-f]{64}$'),
 subject_id text NOT NULL UNIQUE CHECK(subject_id ~ '^visitor_[0-9a-f]{64}$')
);
ALTER TABLE nku_identity_pilot_v1.browser_visitors ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.browser_visitors FROM PUBLIC,anon,authenticated,service_role;
ALTER FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) RENAME TO nku_identity_pilot_v1_before_visitors_rpc;
CREATE FUNCTION public.nku_identity_pilot_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; owner text; k text; d nku_identity_pilot_v1.agent_devices%ROWTYPE;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>900000 THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF op='visitor_probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','browser-visitor-v1')); END IF;
 IF op='configure_subjects' THEN
  -- Preserve private visitors across restarts; keep the original registered roster gate.
  IF (SELECT count(*) FROM jsonb_object_keys(args))<>1 OR jsonb_typeof(args->'subjects') IS DISTINCT FROM 'array' THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  IF jsonb_array_length(args->'subjects')<>2 OR EXISTS(SELECT 1 FROM jsonb_array_elements(args->'subjects') x
   WHERE jsonb_typeof(x)<>'string' OR trim(both '"' from x::text) !~ '^cloudbase_pilot_[0-9a-f]{64}$')
   OR (SELECT count(DISTINCT x) FROM jsonb_array_elements_text(args->'subjects') x)<>2 THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  PERFORM pg_advisory_xact_lock(604022001);
  DELETE FROM nku_identity_pilot_v1.approved_subjects a WHERE a.subject_id NOT IN
   (SELECT jsonb_array_elements_text(args->'subjects')) AND NOT EXISTS
   (SELECT 1 FROM nku_identity_pilot_v1.browser_visitors v WHERE v.subject_id=a.subject_id);
  INSERT INTO nku_identity_pilot_v1.approved_subjects SELECT jsonb_array_elements_text(args->'subjects') ON CONFLICT DO NOTHING;
  DELETE FROM nku_identity_pilot_v1.browser_sessions WHERE owner_subject_id NOT IN
   (SELECT subject_id FROM nku_identity_pilot_v1.approved_subjects);
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('configured',true));
 END IF;
 IF op='visitor_status' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(args))<>1 OR coalesce(args->>'session_hash','') !~ '^[0-9a-f]{64}$' THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  result:=public.nku_identity_pilot_v1_before_visitors_rpc('get_workspace',args);
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('visitor',EXISTS(
   SELECT 1 FROM nku_identity_pilot_v1.browser_visitors v JOIN nku_identity_pilot_v1.browser_sessions s
    ON s.owner_subject_id=v.subject_id WHERE s.token_hash=args->>'session_hash')));
 END IF;
 IF op='visitor_begin' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(args))<>6 OR NOT args ?& ARRAY[
   'challenge_hash','code_hash','subject_id','token_hash','csrf_hash','workspace_ref'] THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  FOREACH k IN ARRAY ARRAY['challenge_hash','code_hash','token_hash','csrf_hash'] LOOP
   IF jsonb_typeof(args->k) IS DISTINCT FROM 'string' OR coalesce(args->>k,'') !~ '^[0-9a-f]{64}$' THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  END LOOP;
  IF coalesce(args->>'subject_id','') !~ '^visitor_[0-9a-f]{64}$' OR coalesce(args->>'workspace_ref','') !~ '^pilot_workspace_[A-Za-z0-9_-]{24}$' THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  PERFORM pg_advisory_xact_lock(604022001);
  SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE challenge_hash=args->>'challenge_hash' FOR UPDATE;
  SELECT subject_id INTO owner FROM nku_identity_pilot_v1.browser_visitors WHERE challenge_hash=args->>'challenge_hash';
  IF d.challenge_hash IS NOT NULL AND (d.code_hash<>args->>'code_hash' OR
   (d.owner_subject_id IS NOT NULL AND d.owner_subject_id IS DISTINCT FROM owner)) THEN
   RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF owner IS NOT NULL AND (SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions WHERE owner_subject_id=owner)>=20 THEN
   RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
  IF owner IS NULL THEN
   IF (SELECT count(*) FROM nku_identity_pilot_v1.browser_visitors)>=5000 THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
   owner:=args->>'subject_id';
   INSERT INTO nku_identity_pilot_v1.browser_visitors VALUES(args->>'challenge_hash',owner);
   INSERT INTO nku_identity_pilot_v1.approved_subjects VALUES(owner);
  ELSIF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=owner) THEN
   RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  result:=public.nku_identity_pilot_v1_before_visitors_rpc('login',jsonb_build_object(
   'subject_id',owner,'token_hash',args->>'token_hash','csrf_hash',args->>'csrf_hash',
   'workspace_ref',args->>'workspace_ref','previous_session_hash',repeat('0',64),'persistent',true));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'visitor login rejected'; END IF;
  IF (public.nku_agent_device_v1_rpc('register',jsonb_build_object('challenge_hash',args->>'challenge_hash',
   'code_hash',args->>'code_hash','session_hash',args->>'token_hash')))->'ok' IS DISTINCT FROM 'true'::jsonb THEN
   RAISE EXCEPTION 'visitor device registration rejected'; END IF;
  RETURN result;
 END IF;
 RETURN public.nku_identity_pilot_v1_before_visitors_rpc(op,args);
END $$;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_before_visitors_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) TO service_role;
COMMIT;
