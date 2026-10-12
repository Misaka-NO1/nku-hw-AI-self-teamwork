-- Additive module-credit storage and explicitly consented degree:read.
-- Run once after agent-device/native migrations. Never upgrade existing grants.
BEGIN;
ALTER FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb)
 RENAME TO nku_competition_oauth_v1_before_degree_rpc;
CREATE FUNCTION public.nku_competition_oauth_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; requested text; baseline text;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 requested:=args->>'scopes';
 IF op='authorize_start' AND requested IN ('demo:read degree:read',
  'demo:read tasks:read degree:read','demo:read tasks:read tasks:write degree:read',
  'demo:read devices:bind degree:read','demo:read tasks:read devices:bind degree:read',
  'demo:read tasks:read tasks:write devices:bind degree:read') THEN
  baseline:=replace(requested,' degree:read','');
  result:=public.nku_competition_oauth_v1_before_degree_rpc(op,jsonb_set(args,'{scopes}',to_jsonb(baseline)));
  IF result->'ok'='true'::jsonb THEN
   UPDATE nku_competition_oauth_v1.requests SET scopes=string_to_array(requested,' ')
    WHERE transaction_hash=args->>'transaction_hash' AND source_session_hash=args->>'session_hash' AND decision IS NULL;
   IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('scopes',to_jsonb(string_to_array(requested,' '))));
  END IF;
  RETURN result;
 END IF;
 RETURN public.nku_competition_oauth_v1_before_degree_rpc(op,args);
END $$;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_before_degree_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) TO service_role;

CREATE SCHEMA nku_degree_progress_v1;
REVOKE ALL ON SCHEMA nku_degree_progress_v1 FROM PUBLIC,anon,authenticated,service_role;
CREATE TABLE nku_degree_progress_v1.reports (
 owner_subject_id text PRIMARY KEY, report jsonb NOT NULL,
 revision integer NOT NULL CHECK(revision>0), confirmed_epoch bigint NOT NULL
);
CREATE TABLE nku_degree_progress_v1.idempotency (
 owner_subject_id text NOT NULL, key text NOT NULL, request_hash text NOT NULL, response jsonb NOT NULL,
 PRIMARY KEY(owner_subject_id,key)
);
ALTER TABLE nku_degree_progress_v1.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_degree_progress_v1.idempotency ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_degree_progress_v1 FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.nku_degree_progress_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 g nku_competition_oauth_v1.grants%ROWTYPE; t nku_degree_progress_v1.reports%ROWTYPE;
 idem nku_degree_progress_v1.idempotency%ROWTYPE;
 auth_keys text[]; expected text[]; owner text; state jsonb; result jsonb; c jsonb; m jsonb;
 now_s bigint:=floor(extract(epoch FROM clock_timestamp())); k text; v jsonb;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','degree-progress-v1')); END IF;
 auth_keys:=CASE args->>'principal_kind'
  WHEN 'browser' THEN ARRAY['principal_kind','session_hash','csrf_hash']
  WHEN 'agent' THEN ARRAY['principal_kind','grant_mode','grant_hash','audience'] ELSE NULL END;
 expected:=CASE op WHEN 'read' THEN ARRAY[]::text[]
  WHEN 'save' THEN ARRAY['report','expected_revision','expected_workspace_ref','confirmed','key','request_hash'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>150000
  OR auth_keys IS NULL OR expected IS NULL
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(auth_keys||expected)
  OR NOT args ?& (auth_keys||expected) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF args->>'principal_kind'='browser' THEN
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
 ELSE
  IF args->>'grant_mode'<>'competition' OR op<>'read' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
   AND audience=args->>'audience' AND expires_at>now_s;
  IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  IF NOT 'degree:read'=ANY(g.scopes) THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash;
 END IF;
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 owner:=s.owner_subject_id;
 PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022006));
 state:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
 IF state->>'ok' IS DISTINCT FROM 'true' THEN RETURN state; END IF;
 IF args->>'principal_kind'='agent' THEN
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
   AND audience=args->>'audience' AND expires_at>floor(extract(epoch FROM clock_timestamp())) FOR UPDATE;
  IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  IF NOT 'degree:read'=ANY(g.scopes) THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 END IF;
 SELECT * INTO t FROM nku_degree_progress_v1.reports WHERE owner_subject_id=owner;
 IF op='read' THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object(
  'report',t.report,'revision',coalesce(t.revision,0),'confirmed_epoch',t.confirmed_epoch)); END IF;
 IF s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' OR
  state->'data'->>'workspace_ref' IS DISTINCT FROM args->>'expected_workspace_ref'
  THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF args->'confirmed' IS DISTINCT FROM 'true'::jsonb THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
 IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$'
  OR coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$'
  OR jsonb_typeof(args->'expected_revision') IS DISTINCT FROM 'number'
  OR coalesce(args->>'expected_revision','') !~ '^[0-9]{1,10}$'
  OR (args->>'expected_revision')::bigint>2147483646 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 SELECT * INTO idem FROM nku_degree_progress_v1.idempotency WHERE owner_subject_id=owner AND key=args->>'key';
 IF FOUND THEN
  IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  RETURN jsonb_build_object('ok',true,'data',idem.response);
 END IF;
 IF coalesce(t.revision,0)<>(args->>'expected_revision')::integer THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 c:=args->'report';
 IF jsonb_typeof(c) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(c))<>7
  OR NOT c ?& ARRAY['schema_version','kind','program','cohort','summary','modules','has_in_progress_courses']
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF c->>'schema_version' IS DISTINCT FROM '1.0.0' OR c->>'kind' IS DISTINCT FROM 'degree_credit_progress'
  OR jsonb_typeof(c->'has_in_progress_courses') IS DISTINCT FROM 'boolean'
  OR jsonb_typeof(c->'modules') IS DISTINCT FROM 'array'
  OR jsonb_array_length(c->'modules') NOT BETWEEN 1 AND 200
  OR jsonb_typeof(c->'summary') IS DISTINCT FROM 'object'
  OR (SELECT count(*) FROM jsonb_object_keys(c->'summary'))<>6
  OR NOT (c->'summary') ?& ARRAY['required_credits','completed_credits','actual_credits','reported_result','reviewed_at','note']
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 FOR k,v IN SELECT * FROM jsonb_each(c->'summary') LOOP
  IF k IN ('required_credits','completed_credits','actual_credits') AND v<>'null'::jsonb THEN
   IF jsonb_typeof(v)<>'string' OR v#>>'{}' !~ '^(0|[1-9][0-9]{0,2})(\.[0-9]{1,2})?$' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
   IF (v#>>'{}')::numeric>300 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  ELSIF v<>'null'::jsonb AND (jsonb_typeof(v)<>'string' OR length(v#>>'{}') NOT BETWEEN 1 AND 300) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END LOOP;
 FOR k IN SELECT unnest(ARRAY['program','cohort']) LOOP
  IF c->k<>'null'::jsonb AND (jsonb_typeof(c->k)<>'string' OR length(c->>k) NOT BETWEEN 1 AND 300) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END LOOP;
 FOR m IN SELECT value FROM jsonb_array_elements(c->'modules') LOOP
  IF jsonb_typeof(m)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(m))<>5
   OR NOT m ?& ARRAY['title','required_credits','school_actual_credits','school_status','school_note']
   OR jsonb_typeof(m->'title')<>'string' OR length(m->>'title') NOT BETWEEN 1 AND 300 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  FOR k IN SELECT unnest(ARRAY['required_credits','school_actual_credits']) LOOP
   IF jsonb_typeof(m->k)<>'string' OR coalesce(m->>k,'') !~ '^(0|[1-9][0-9]{0,2})(\.[0-9]{1,2})?$' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
   IF (m->>k)::numeric>300 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  END LOOP;
  FOR k IN SELECT unnest(ARRAY['school_status','school_note']) LOOP
   IF m->k<>'null'::jsonb AND (jsonb_typeof(m->k)<>'string' OR length(m->>k) NOT BETWEEN 1 AND 300) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  END LOOP;
 END LOOP;
 INSERT INTO nku_degree_progress_v1.reports VALUES(owner,c,coalesce(t.revision,0)+1,now_s)
  ON CONFLICT(owner_subject_id) DO UPDATE SET report=excluded.report,revision=excluded.revision,confirmed_epoch=excluded.confirmed_epoch;
 result:=jsonb_build_object('revision',coalesce(t.revision,0)+1,'confirmed_epoch',now_s);
 INSERT INTO nku_degree_progress_v1.idempotency VALUES(owner,args->>'key',args->>'request_hash',result);
 RETURN jsonb_build_object('ok',true,'data',result);
END $$;
REVOKE ALL ON FUNCTION public.nku_degree_progress_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_degree_progress_v1_rpc(text,jsonb) TO service_role;
COMMIT;
