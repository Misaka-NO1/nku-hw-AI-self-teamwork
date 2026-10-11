-- Candidate migration: not deployed as of 2026-10-11.
-- Local routes are feature-gated off by default; never re-run this migration.
-- Dedicated authenticated native integration and hidden SYS_USERID are required.
-- Run only after identity-first guard; never restore anonymous enrollment.
BEGIN;
CREATE TABLE nku_identity_pilot_v1.native_identity_accounts (
 identity_hash text PRIMARY KEY CHECK(identity_hash ~ '^[0-9a-f]{64}$'),
 owner_subject_id text NOT NULL UNIQUE REFERENCES nku_identity_pilot_v1.owner_workspaces(subject_id)
);
ALTER TABLE nku_identity_pilot_v1.native_identity_accounts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.native_identity_accounts FROM PUBLIC,anon,authenticated,service_role;
CREATE FUNCTION public.nku_native_identity_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE expected text[]; k text; owner text; ws text; d nku_identity_pilot_v1.agent_devices%ROWTYPE;
 g nku_competition_oauth_v1.grants%ROWTYPE; s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','native-identity-registry-v1')); END IF;
 expected:=CASE op WHEN 'lookup' THEN ARRAY['identity_hash']
  WHEN 'create' THEN ARRAY['identity_hash','code_hash','workspace_ref','confirmed']
  WHEN 'adopt' THEN ARRAY['identity_hash','grant_hash','audience','confirmed'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>2048 OR expected IS NULL
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected) OR NOT args ?& expected
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 FOREACH k IN ARRAY expected LOOP
  IF k LIKE '%hash' AND (jsonb_typeof(args->k) IS DISTINCT FROM 'string'
   OR coalesce(args->>k,'') !~ '^[0-9a-f]{64}$') THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END LOOP;
 IF op<>'lookup' AND args->'confirmed' IS DISTINCT FROM 'true'::jsonb
  THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
 IF op='create' AND (jsonb_typeof(args->'workspace_ref') IS DISTINCT FROM 'string'
  OR coalesce(args->>'workspace_ref','') !~ '^pilot_workspace_[A-Za-z0-9_-]{24}$')
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 -- Shared with legacy visitor creation/resume. Atomic lookup + create/adoption;
 -- global lock also serializes unique-owner adoption across different identities.
 PERFORM pg_advisory_xact_lock(604022001);
 SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.native_identity_accounts
  WHERE identity_hash=args->>'identity_hash';
 IF op='adopt' THEN
  IF jsonb_typeof(args->'audience') IS DISTINCT FROM 'string' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
   AND audience=args->>'audience' AND expires_at>now_s AND 'devices:bind'=ANY(scopes);
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash
   AND expires_at>now_s AND device_source_session_hash IS NULL;
  IF g.token_hash IS NULL OR s.token_hash IS NULL OR NOT EXISTS(
   SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=s.owner_subject_id)
   THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  IF (owner IS NOT NULL AND owner<>s.owner_subject_id) OR EXISTS(
   SELECT 1 FROM nku_identity_pilot_v1.native_identity_accounts
   WHERE owner_subject_id=s.owner_subject_id AND identity_hash<>args->>'identity_hash')
   THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT workspace_ref INTO ws FROM nku_identity_pilot_v1.owner_workspaces WHERE subject_id=s.owner_subject_id;
  IF ws IS DISTINCT FROM s.workspace_ref THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  owner:=s.owner_subject_id;
  INSERT INTO nku_identity_pilot_v1.native_identity_accounts VALUES(args->>'identity_hash',owner) ON CONFLICT DO NOTHING;
 END IF;
 IF op='create' THEN
  SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE code_hash=args->>'code_hash' FOR UPDATE;
  IF d.challenge_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF d.owner_subject_id IS NOT NULL AND d.owner_subject_id IS DISTINCT FROM owner
   THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF owner IS NULL THEN
   IF (SELECT count(*) FROM nku_identity_pilot_v1.native_identity_accounts)>=5000
    THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
   owner:='visitor_'||(args->>'identity_hash'); ws:=args->>'workspace_ref';
   IF EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=owner)
    OR EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_visitors WHERE challenge_hash=d.challenge_hash)
    THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   INSERT INTO nku_identity_pilot_v1.approved_subjects VALUES(owner);
   INSERT INTO nku_identity_pilot_v1.workspaces VALUES(ws,owner,'demo-v1',253370736000);
   INSERT INTO nku_identity_pilot_v1.owner_workspaces VALUES(owner,ws);
   -- Empty visitor data path, never copy another owner's fixture/course/task.
   INSERT INTO nku_identity_pilot_v1.browser_visitors VALUES(d.challenge_hash,owner);
   INSERT INTO nku_identity_pilot_v1.native_identity_accounts VALUES(args->>'identity_hash',owner);
   RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('has_space',true,'created',true,'workspace_ref',ws));
  END IF;
 END IF;
 IF owner IS NULL THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('has_space',false,'created',false)); END IF;
 SELECT w.workspace_ref INTO ws FROM nku_identity_pilot_v1.owner_workspaces ow
  JOIN nku_identity_pilot_v1.workspaces w ON w.workspace_ref=ow.workspace_ref AND w.owner_subject_id=ow.subject_id
  JOIN nku_identity_pilot_v1.approved_subjects a ON a.subject_id=ow.subject_id
  WHERE ow.subject_id=owner AND w.expires_at>now_s;
 IF ws IS NULL THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('has_space',true,'created',false,'workspace_ref',ws));
END $$;
REVOKE ALL ON FUNCTION public.nku_native_identity_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_native_identity_v1_rpc(text,jsonb) TO service_role;
COMMIT;
