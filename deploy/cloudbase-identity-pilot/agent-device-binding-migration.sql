-- Additive fixed browser identity + explicitly consented Agent binding.
-- Run AFTER persistent-auth, personal-schedules and device-login migrations.
-- No existing grant upgrades, owner changes, or expiry extensions.
BEGIN;
ALTER FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb)
 RENAME TO nku_competition_oauth_v1_before_devices_rpc;
CREATE FUNCTION public.nku_competition_oauth_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; requested text; baseline text;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 requested:=args->>'scopes';
 IF op='authorize_start' AND requested IN ('demo:read devices:bind',
  'demo:read tasks:read devices:bind','demo:read tasks:read tasks:write devices:bind') THEN
  baseline:=replace(requested,' devices:bind','');
  result:=public.nku_competition_oauth_v1_before_devices_rpc(op,jsonb_set(args,'{scopes}',to_jsonb(baseline)));
  IF result->'ok'='true'::jsonb THEN
   UPDATE nku_competition_oauth_v1.requests SET scopes=string_to_array(requested,' ')
    WHERE transaction_hash=args->>'transaction_hash' AND source_session_hash=args->>'session_hash' AND decision IS NULL;
   RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('scopes',to_jsonb(string_to_array(requested,' '))));
  END IF;
  RETURN result;
 END IF;
 RETURN public.nku_competition_oauth_v1_before_devices_rpc(op,args);
END $$;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_before_devices_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) TO service_role;

ALTER TABLE nku_identity_pilot_v1.browser_sessions ADD COLUMN agent_device_grant_hash text
 REFERENCES nku_competition_oauth_v1.grants(token_hash) ON DELETE CASCADE;
CREATE TABLE nku_identity_pilot_v1.agent_devices (
 challenge_hash text PRIMARY KEY CHECK(challenge_hash ~ '^[0-9a-f]{64}$'),
 code_hash text NOT NULL UNIQUE CHECK(code_hash ~ '^[0-9a-f]{64}$'),
 owner_subject_id text,
 grant_hash text REFERENCES nku_competition_oauth_v1.grants(token_hash) ON DELETE SET NULL,
 child_session_hash text REFERENCES nku_identity_pilot_v1.browser_sessions(token_hash) ON DELETE SET NULL
);
ALTER TABLE nku_identity_pilot_v1.agent_devices ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.agent_devices FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION nku_identity_pilot_v1.expire_agent_device_sessions() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
 IF NEW.expires_at<OLD.expires_at THEN
  UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=least(expires_at,NEW.expires_at)
   WHERE agent_device_grant_hash=NEW.token_hash;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER expire_agent_device_sessions AFTER UPDATE OF expires_at ON nku_competition_oauth_v1.grants
 FOR EACH ROW EXECUTE FUNCTION nku_identity_pilot_v1.expire_agent_device_sessions();
-- Explicit device logout does not immediately resurrect its login on reload.
CREATE FUNCTION nku_identity_pilot_v1.detach_agent_device_session() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
 UPDATE nku_identity_pilot_v1.agent_devices SET grant_hash=NULL
  WHERE child_session_hash=OLD.token_hash;
 RETURN OLD;
END $$;
CREATE TRIGGER detach_agent_device_session BEFORE DELETE ON nku_identity_pilot_v1.browser_sessions
 FOR EACH ROW EXECUTE FUNCTION nku_identity_pilot_v1.detach_agent_device_session();
REVOKE ALL ON FUNCTION nku_identity_pilot_v1.expire_agent_device_sessions(),
 nku_identity_pilot_v1.detach_agent_device_session() FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.nku_agent_device_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE now_s bigint:=floor(extract(epoch FROM clock_timestamp())); expected text[]; k text;
 d nku_identity_pilot_v1.agent_devices%ROWTYPE;
 g nku_competition_oauth_v1.grants%ROWTYPE;
 s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 w nku_identity_pilot_v1.workspaces%ROWTYPE; result jsonb; expiry bigint;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','agent-device-v1')); END IF;
 expected:=CASE op WHEN 'start' THEN ARRAY['challenge_hash','code_hash']
  WHEN 'register' THEN ARRAY['challenge_hash','code_hash','session_hash']
  WHEN 'status' THEN ARRAY['challenge_hash','session_hash']
  WHEN 'detach' THEN ARRAY['challenge_hash','session_hash','csrf_hash']
  WHEN 'bind' THEN ARRAY['grant_hash','audience','code_hash','confirm_binding']
  WHEN 'claim' THEN ARRAY['challenge_hash','token_hash','csrf_hash'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>4096 OR expected IS NULL
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected) OR NOT args ?& expected
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 FOREACH k IN ARRAY expected LOOP
  IF k NOT IN ('audience','confirm_binding') AND (jsonb_typeof(args->k) IS DISTINCT FROM 'string'
   OR coalesce(args->>k,'') !~ '^[0-9a-f]{64}$') THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END LOOP;
 IF op IN ('start','register') THEN
  IF op='register' THEN
   SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
   result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',args->>'session_hash'));
   IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  END IF;
  IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.agent_devices WHERE challenge_hash=args->>'challenge_hash')
   AND (SELECT count(*) FROM nku_identity_pilot_v1.agent_devices)>=10000 THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
  INSERT INTO nku_identity_pilot_v1.agent_devices(challenge_hash,code_hash)
   VALUES(args->>'challenge_hash',args->>'code_hash') ON CONFLICT DO NOTHING;
  IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.agent_devices
   WHERE challenge_hash=args->>'challenge_hash' AND code_hash=args->>'code_hash') THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF op='register' THEN
   SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE challenge_hash=args->>'challenge_hash' FOR UPDATE;
   IF d.owner_subject_id IS NOT NULL AND d.owner_subject_id<>s.owner_subject_id THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
   -- Existing valid tool login fixes the device owner; Agent cannot replace it.
   UPDATE nku_identity_pilot_v1.agent_devices SET owner_subject_id=s.owner_subject_id WHERE challenge_hash=d.challenge_hash;
  END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','ready'));
 END IF;
 IF op IN ('status','detach') THEN
  SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE challenge_hash=args->>'challenge_hash';
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
  result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  IF op='detach' THEN
   IF s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
   IF d.challenge_hash IS NOT NULL AND d.owner_subject_id IS DISTINCT FROM s.owner_subject_id THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
   UPDATE nku_identity_pilot_v1.agent_devices SET grant_hash=NULL WHERE challenge_hash=d.challenge_hash;
   IF d.child_session_hash IS NOT NULL AND d.child_session_hash<>s.token_hash THEN
    DELETE FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=d.child_session_hash AND owner_subject_id=s.owner_subject_id;
   END IF;
   RETURN jsonb_build_object('ok',true,'data','{}'::jsonb);
  END IF;
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=d.grant_hash AND expires_at>now_s;
  IF g.token_hash IS NULL THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','pending')); END IF;
  IF s.owner_subject_id IS DISTINCT FROM d.owner_subject_id THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF NOT 'devices:bind'=ANY(g.scopes) OR NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions
   WHERE token_hash=g.source_session_hash AND owner_subject_id=s.owner_subject_id AND workspace_ref=s.workspace_ref AND expires_at>now_s)
   THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','bound','workspace_ref',s.workspace_ref));
 END IF;
 IF op='bind' THEN
  IF args->'confirm_binding' IS DISTINCT FROM 'true'::jsonb THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
  IF jsonb_typeof(args->'audience') IS DISTINCT FROM 'string' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash' AND audience=args->>'audience' AND expires_at>now_s;
  IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  IF NOT 'devices:bind'=ANY(g.scopes) THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash;
  IF s.token_hash IS NULL OR s.device_source_session_hash IS NOT NULL THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(s.owner_subject_id,604022002));
  result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE code_hash=args->>'code_hash' FOR UPDATE;
  IF d.challenge_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF d.owner_subject_id IS NOT NULL AND d.owner_subject_id<>s.owner_subject_id THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF d.child_session_hash IS NOT NULL THEN
   IF d.grant_hash IS DISTINCT FROM g.token_hash THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  END IF;
  UPDATE nku_identity_pilot_v1.agent_devices SET owner_subject_id=s.owner_subject_id,grant_hash=g.token_hash WHERE challenge_hash=d.challenge_hash;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','authorized','workspace_ref',s.workspace_ref));
 END IF;
 SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE challenge_hash=args->>'challenge_hash';
 IF d.challenge_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 IF d.grant_hash IS NULL THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','pending')); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(d.owner_subject_id,604022002));
 SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE challenge_hash=args->>'challenge_hash' FOR UPDATE;
 SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=d.grant_hash AND expires_at>now_s;
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash;
 IF g.token_hash IS NULL OR s.token_hash IS NULL OR s.owner_subject_id IS DISTINCT FROM d.owner_subject_id
  OR s.device_source_session_hash IS NOT NULL OR NOT 'devices:bind'=ANY(g.scopes)
  THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
 IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
 IF d.child_session_hash IS NOT NULL THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 IF (SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions WHERE device_source_session_hash=s.token_hash)>=20
  THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
 SELECT * INTO w FROM nku_identity_pilot_v1.workspaces WHERE workspace_ref=s.workspace_ref AND owner_subject_id=s.owner_subject_id;
 expiry:=least(g.expires_at,s.expires_at,w.expires_at);
 INSERT INTO nku_identity_pilot_v1.browser_sessions(token_hash,owner_subject_id,workspace_ref,csrf_hash,expires_at,device_source_session_hash,agent_device_grant_hash)
  VALUES(args->>'token_hash',s.owner_subject_id,s.workspace_ref,args->>'csrf_hash',expiry,s.token_hash,g.token_hash);
 UPDATE nku_identity_pilot_v1.agent_devices SET child_session_hash=args->>'token_hash' WHERE challenge_hash=d.challenge_hash;
 RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','bound','workspace_ref',s.workspace_ref,'expires_epoch',expiry));
END $$;
REVOKE ALL ON FUNCTION public.nku_agent_device_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_agent_device_v1_rpc(text,jsonb) TO service_role;
COMMIT;
