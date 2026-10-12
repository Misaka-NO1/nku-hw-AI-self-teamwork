-- Additive Agent upload/confirmation. Run once AFTER degree-progress-migration.sql.
-- Never replay old migrations; never expand an existing OAuth grant.
BEGIN;
ALTER FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb)
 RENAME TO nku_competition_oauth_v1_before_degree_agent_rpc;
CREATE FUNCTION public.nku_competition_oauth_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; requested text;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 requested:=args->>'scopes';
 IF op='authorize_start' AND requested IN (
  'demo:read degree:read degree:write','demo:read tasks:read degree:read degree:write',
  'demo:read tasks:read tasks:write degree:read degree:write',
  'demo:read devices:bind degree:read degree:write','demo:read tasks:read devices:bind degree:read degree:write',
  'demo:read tasks:read tasks:write devices:bind degree:read degree:write') THEN
  result:=public.nku_competition_oauth_v1_before_degree_agent_rpc(op,
   jsonb_set(args,'{scopes}',to_jsonb(replace(requested,' degree:write',''))));
  IF result->'ok'='true'::jsonb THEN
   UPDATE nku_competition_oauth_v1.requests SET scopes=string_to_array(requested,' ')
    WHERE transaction_hash=args->>'transaction_hash' AND source_session_hash=args->>'session_hash' AND decision IS NULL;
   IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('scopes',to_jsonb(string_to_array(requested,' '))));
  END IF;
  RETURN result;
 END IF;
 RETURN public.nku_competition_oauth_v1_before_degree_agent_rpc(op,args);
END $$;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_before_degree_agent_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) TO service_role;

CREATE TABLE nku_degree_progress_v1.agent_drafts (
 draft_id text PRIMARY KEY, owner_subject_id text NOT NULL, report jsonb NOT NULL,
 payload_hash text NOT NULL, expected_revision integer NOT NULL, workspace_ref text NOT NULL,
 expires_epoch bigint NOT NULL, response jsonb
);
ALTER TABLE nku_degree_progress_v1.agent_drafts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE nku_degree_progress_v1.agent_drafts FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION nku_degree_progress_v1.valid_report(c jsonb) RETURNS boolean
LANGUAGE plpgsql SET search_path='' AS $$
DECLARE k text; v jsonb; m jsonb;
BEGIN
 IF jsonb_typeof(c) IS DISTINCT FROM 'object' OR octet_length(c::text)>131072 OR (SELECT count(*) FROM jsonb_object_keys(c))<>7
  OR NOT c ?& ARRAY['schema_version','kind','program','cohort','summary','modules','has_in_progress_courses']
  THEN RETURN false; END IF;
 IF c->>'schema_version' IS DISTINCT FROM '1.0.0' OR c->>'kind' IS DISTINCT FROM 'degree_credit_progress'
  OR jsonb_typeof(c->'has_in_progress_courses') IS DISTINCT FROM 'boolean'
  OR jsonb_typeof(c->'modules') IS DISTINCT FROM 'array'
  OR jsonb_array_length(c->'modules') NOT BETWEEN 1 AND 200
  OR jsonb_typeof(c->'summary') IS DISTINCT FROM 'object'
  OR (SELECT count(*) FROM jsonb_object_keys(c->'summary'))<>6
  OR NOT (c->'summary') ?& ARRAY['required_credits','completed_credits','actual_credits','reported_result','reviewed_at','note']
  THEN RETURN false; END IF;
 FOR k,v IN SELECT * FROM jsonb_each(c->'summary') LOOP
  IF k IN ('required_credits','completed_credits','actual_credits') AND v<>'null'::jsonb THEN
   IF jsonb_typeof(v) IS DISTINCT FROM 'string' OR v#>>'{}' !~ '^(0|[1-9][0-9]{0,2})(\.[0-9]{1,2})?$' THEN RETURN false; END IF;
   IF (v#>>'{}')::numeric>300 THEN RETURN false; END IF;
  ELSIF v<>'null'::jsonb AND (jsonb_typeof(v) IS DISTINCT FROM 'string' OR length(v#>>'{}') NOT BETWEEN 1 AND 300) THEN RETURN false; END IF;
 END LOOP;
 FOR k IN SELECT unnest(ARRAY['program','cohort']) LOOP
  IF c->k<>'null'::jsonb AND (jsonb_typeof(c->k) IS DISTINCT FROM 'string' OR length(c->>k) NOT BETWEEN 1 AND 300) THEN RETURN false; END IF;
 END LOOP;
 FOR m IN SELECT value FROM jsonb_array_elements(c->'modules') LOOP
  IF jsonb_typeof(m) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(m))<>5
   OR NOT m ?& ARRAY['title','required_credits','school_actual_credits','school_status','school_note']
   OR jsonb_typeof(m->'title') IS DISTINCT FROM 'string' OR length(m->>'title') NOT BETWEEN 1 AND 300 THEN RETURN false; END IF;
  FOR k IN SELECT unnest(ARRAY['required_credits','school_actual_credits']) LOOP
   IF jsonb_typeof(m->k) IS DISTINCT FROM 'string' OR coalesce(m->>k,'') !~ '^(0|[1-9][0-9]{0,2})(\.[0-9]{1,2})?$' THEN RETURN false; END IF;
   IF (m->>k)::numeric>300 THEN RETURN false; END IF;
  END LOOP;
  FOR k IN SELECT unnest(ARRAY['school_status','school_note']) LOOP
   IF m->k<>'null'::jsonb AND (jsonb_typeof(m->k) IS DISTINCT FROM 'string' OR length(m->>k) NOT BETWEEN 1 AND 300) THEN RETURN false; END IF;
  END LOOP;
 END LOOP;

 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
REVOKE ALL ON FUNCTION nku_degree_progress_v1.valid_report(jsonb) FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.nku_degree_agent_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE g nku_competition_oauth_v1.grants%ROWTYPE; s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 d nku_degree_progress_v1.agent_drafts%ROWTYPE; t nku_degree_progress_v1.reports%ROWTYPE;
 state jsonb; result jsonb; expected text[]; owner text;
 now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','degree-agent-v1')); END IF;
 expected:=CASE op WHEN 'prepare' THEN ARRAY['report','draft_id','payload_hash']
  WHEN 'confirm' THEN ARRAY['draft_id','payload_hash','confirmed'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>150000 OR expected IS NULL
  OR NOT args ?& (ARRAY['grant_hash','audience']||expected)
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected)+2
  OR coalesce(args->>'draft_id','') !~ '^degree_[0-9a-f]{32}$'
  OR coalesce(args->>'payload_hash','') !~ '^[0-9a-f]{64}$'
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
  AND audience=args->>'audience' AND expires_at>now_s;
 IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 IF NOT ('degree:write'=ANY(g.scopes) AND 'degree:read'=ANY(g.scopes))
  THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash;
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 owner:=s.owner_subject_id;
 PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022006));
 state:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
 IF state->>'ok' IS DISTINCT FROM 'true' THEN RETURN state; END IF;
 SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
  AND audience=args->>'audience' AND expires_at>floor(extract(epoch FROM clock_timestamp())) FOR UPDATE;
 IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 IF NOT ('degree:write'=ANY(g.scopes) AND 'degree:read'=ANY(g.scopes))
  THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='prepare' THEN
  IF NOT nku_degree_progress_v1.valid_report(args->'report') THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  -- Bound pending previews, without deleting a saved report or another account.
  IF (SELECT count(*) FROM nku_degree_progress_v1.agent_drafts WHERE owner_subject_id=owner
   AND response IS NULL AND expires_epoch>now_s)>=20 THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
  SELECT * INTO t FROM nku_degree_progress_v1.reports WHERE owner_subject_id=owner;
  INSERT INTO nku_degree_progress_v1.agent_drafts VALUES(args->>'draft_id',owner,args->'report',args->>'payload_hash',
   coalesce(t.revision,0),state->'data'->>'workspace_ref',now_s+600,NULL);
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object(
   'draft_id',args->>'draft_id','payload_hash',args->>'payload_hash','report',args->'report',
   'expected_revision',coalesce(t.revision,0),'replaces_existing',t.report IS NOT NULL,'expires_epoch',now_s+600));
 END IF;
 IF args->'confirmed' IS DISTINCT FROM 'true'::jsonb THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
 SELECT * INTO d FROM nku_degree_progress_v1.agent_drafts WHERE draft_id=args->>'draft_id' AND owner_subject_id=owner FOR UPDATE;
 IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 IF d.payload_hash IS DISTINCT FROM args->>'payload_hash' OR d.workspace_ref IS DISTINCT FROM state->'data'->>'workspace_ref'
  THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 IF d.response IS NOT NULL THEN RETURN jsonb_build_object('ok',true,'data',d.response); END IF;
 IF d.expires_epoch<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
 result:=public.nku_degree_progress_v1_rpc('save',jsonb_build_object(
  'principal_kind','browser','session_hash',s.token_hash,'csrf_hash',s.csrf_hash,
  'report',d.report,'expected_revision',d.expected_revision,'expected_workspace_ref',d.workspace_ref,
  'confirmed',true,'key',d.draft_id,'request_hash',d.payload_hash));
 IF result->>'ok' IS DISTINCT FROM 'true' THEN RETURN result; END IF;
 SELECT * INTO t FROM nku_degree_progress_v1.reports WHERE owner_subject_id=owner;
 IF t.report IS DISTINCT FROM d.report OR t.revision IS DISTINCT FROM (result->'data'->>'revision')::integer
  THEN RAISE EXCEPTION 'degree readback mismatch'; END IF;
 result:=result->'data'||jsonb_build_object('saved',true,'readback_verified',true,'report',t.report);
 UPDATE nku_degree_progress_v1.agent_drafts SET response=result WHERE draft_id=d.draft_id;
 RETURN jsonb_build_object('ok',true,'data',result);
END $$;
REVOKE ALL ON FUNCTION public.nku_degree_agent_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_degree_agent_v1_rpc(text,jsonb) TO service_role;
COMMIT;
