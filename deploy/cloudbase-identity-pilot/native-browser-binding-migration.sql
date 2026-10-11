-- Run ONCE after native-identity-registry-migration.sql; default-off HTTP gate.
-- No existing owner/data/authorization changes. Never mint login by public DEV.
BEGIN;
CREATE TABLE nku_identity_pilot_v1.native_browser_intakes (
 challenge_hash text PRIMARY KEY REFERENCES nku_identity_pilot_v1.agent_devices(challenge_hash),
 identity_hash text NOT NULL CHECK(identity_hash ~ '^[0-9a-f]{64}$'),
 authorized boolean NOT NULL DEFAULT false,
 child_session_hash text REFERENCES nku_identity_pilot_v1.browser_sessions(token_hash) ON DELETE SET NULL
);
ALTER TABLE nku_identity_pilot_v1.native_browser_intakes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.native_browser_intakes FROM PUBLIC,anon,authenticated,service_role;
ALTER TABLE nku_identity_pilot_v1.browser_sessions ADD COLUMN native_device_challenge_hash text
 REFERENCES nku_identity_pilot_v1.native_browser_intakes(challenge_hash);
CREATE FUNCTION nku_identity_pilot_v1.detach_native_session() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
 UPDATE nku_identity_pilot_v1.native_browser_intakes SET authorized=false
 WHERE challenge_hash=OLD.native_device_challenge_hash;
 RETURN OLD;
END $$;
CREATE TRIGGER detach_native_session BEFORE DELETE ON nku_identity_pilot_v1.browser_sessions
 FOR EACH ROW EXECUTE FUNCTION nku_identity_pilot_v1.detach_native_session();
REVOKE ALL ON FUNCTION nku_identity_pilot_v1.detach_native_session() FROM PUBLIC,anon,authenticated,service_role;
CREATE FUNCTION nku_identity_pilot_v1.revoke_native_oauth_sessions() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ DECLARE owner text; BEGIN
 IF TG_OP='DELETE' OR NEW.expires_at<OLD.expires_at THEN
  SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=OLD.source_session_hash;
  UPDATE nku_identity_pilot_v1.native_browser_intakes SET authorized=false WHERE identity_hash IN
   (SELECT identity_hash FROM nku_identity_pilot_v1.native_identity_accounts WHERE owner_subject_id=owner);
  UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0
   WHERE owner_subject_id=owner AND native_device_challenge_hash IS NOT NULL;
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER revoke_native_oauth_sessions BEFORE DELETE OR UPDATE OF expires_at ON nku_competition_oauth_v1.grants
 FOR EACH ROW EXECUTE FUNCTION nku_identity_pilot_v1.revoke_native_oauth_sessions();
REVOKE ALL ON FUNCTION nku_identity_pilot_v1.revoke_native_oauth_sessions() FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.nku_native_browser_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE expected text[]; k text; owner text; ws text; result jsonb; created boolean:=false;
 d nku_identity_pilot_v1.agent_devices%ROWTYPE;
 n nku_identity_pilot_v1.native_browser_intakes%ROWTYPE;
 s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 source nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 g nku_competition_oauth_v1.grants%ROWTYPE;
 now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','native-browser-v1')); END IF;
 expected:=CASE op WHEN 'identify' THEN ARRAY['identity_hash','code_hash']
  WHEN 'verify_grant' THEN ARRAY['identity_hash','grant_hash','audience']
  WHEN 'enroll' THEN ARRAY['identity_hash','code_hash','intent','confirmed','workspace_ref']
  WHEN 'adopt_bind' THEN ARRAY['identity_hash','code_hash','grant_hash','audience','confirmed']
  WHEN 'state' THEN ARRAY['challenge_hash','session_hash']
  WHEN 'claim' THEN ARRAY['challenge_hash','session_hash','token_hash','csrf_hash']
  WHEN 'detach' THEN ARRAY['challenge_hash','session_hash','csrf_hash'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>2048 OR expected IS NULL
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected) OR NOT args ?& expected
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 FOREACH k IN ARRAY expected LOOP
  IF k LIKE '%hash' AND (jsonb_typeof(args->k) IS DISTINCT FROM 'string'
   OR coalesce(args->>k,'') !~ '^[0-9a-f]{64}$') THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END LOOP;
 IF op='verify_grant' THEN
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
   AND audience=args->>'audience' AND expires_at>now_s AND 'demo:read'=ANY(scopes);
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash AND expires_at>now_s;
  SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.native_identity_accounts WHERE identity_hash=args->>'identity_hash';
  IF g.token_hash IS NULL OR s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  IF owner IS NULL OR owner<>s.owner_subject_id THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  result:=public.nku_native_identity_v1_rpc('lookup',jsonb_build_object('identity_hash',args->>'identity_hash'));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  IF s.workspace_ref IS DISTINCT FROM result->'data'->>'workspace_ref' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('owner_consistent',true));
 END IF;
 IF op IN ('enroll','adopt_bind') AND args->'confirmed' IS DISTINCT FROM 'true'::jsonb
  THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
 IF op='enroll' AND (args->>'intent' NOT IN ('create','bind')
  OR jsonb_typeof(args->'intent') IS DISTINCT FROM 'string'
  OR jsonb_typeof(args->'workspace_ref') IS DISTINCT FROM 'string'
  OR args->>'workspace_ref' !~ '^pilot_workspace_[A-Za-z0-9_-]{24}$')
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 PERFORM pg_advisory_xact_lock(604022001);
 SELECT * INTO d FROM nku_identity_pilot_v1.agent_devices WHERE
  CASE WHEN op IN ('identify','enroll','adopt_bind') THEN code_hash=args->>'code_hash'
  ELSE challenge_hash=args->>'challenge_hash' END FOR UPDATE;
 IF d.challenge_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 SELECT * INTO n FROM nku_identity_pilot_v1.native_browser_intakes WHERE challenge_hash=d.challenge_hash FOR UPDATE;
 IF op IN ('identify','enroll','adopt_bind') THEN
  IF n.challenge_hash IS NOT NULL AND n.identity_hash<>args->>'identity_hash'
   THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.native_identity_accounts WHERE identity_hash=args->>'identity_hash';
 ELSE
  IF n.challenge_hash IS NULL THEN RETURN jsonb_build_object('ok',true,'data',
   jsonb_build_object('status','identity_pending','has_space',false,'created',false)); END IF;
  SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.native_identity_accounts WHERE identity_hash=n.identity_hash;
 END IF;
 IF owner IS NOT NULL THEN
  result:=public.nku_native_identity_v1_rpc('lookup',jsonb_build_object('identity_hash',
   CASE WHEN op IN ('identify','enroll','adopt_bind') THEN args->>'identity_hash' ELSE n.identity_hash END));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  ws:=result->'data'->>'workspace_ref';
  IF d.owner_subject_id IS NOT NULL AND d.owner_subject_id<>owner THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 END IF;
 IF op='identify' THEN
  INSERT INTO nku_identity_pilot_v1.native_browser_intakes(challenge_hash,identity_hash)
   VALUES(d.challenge_hash,args->>'identity_hash') ON CONFLICT DO NOTHING;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status',
   CASE WHEN owner IS NOT NULL THEN 'existing_space' WHEN d.owner_subject_id IS NOT NULL THEN 'legacy_authorization_required'
   ELSE 'first_use_confirmation' END,'has_space',owner IS NOT NULL,'created',false,'workspace_ref',ws));
 END IF;
 IF op IN ('enroll','adopt_bind') THEN
  -- Identity lookup MUST precede confirmation. Public code alone is insufficient.
  IF n.challenge_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
  IF op='enroll' THEN
   IF owner IS NULL AND d.owner_subject_id IS NOT NULL THEN RETURN jsonb_build_object('ok',true,'data',
    jsonb_build_object('status','legacy_authorization_required','has_space',false,'created',false)); END IF;
   IF owner IS NULL AND args->>'intent'='bind' THEN RETURN jsonb_build_object('ok',true,'data',
    jsonb_build_object('status','first_use_confirmation','has_space',false,'created',false)); END IF;
   result:=public.nku_native_identity_v1_rpc('create',jsonb_build_object('identity_hash',args->>'identity_hash',
    'code_hash',args->>'code_hash','workspace_ref',args->>'workspace_ref','confirmed',true));
   IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
   created:=(result->'data'->>'created')::boolean; ws:=result->'data'->>'workspace_ref';
   SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.native_identity_accounts WHERE identity_hash=args->>'identity_hash';
  ELSE
   -- Adoption and the old OAuth device bind are one subtransaction. A failed
   -- bind rolls back the mapping too; no partial account association persists.
   BEGIN
    SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
     AND audience=args->>'audience' AND expires_at>now_s;
    SELECT * INTO source FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash AND expires_at>now_s;
    IF source.token_hash IS NULL OR (d.owner_subject_id IS NOT NULL AND d.owner_subject_id<>source.owner_subject_id)
     THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
    result:=public.nku_native_identity_v1_rpc('adopt',args-ARRAY['code_hash']);
    IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION USING ERRCODE='P0001'; END IF;
    ws:=result->'data'->>'workspace_ref';
    result:=public.nku_agent_device_v1_rpc('bind',jsonb_build_object('grant_hash',args->>'grant_hash',
     'audience',args->>'audience','code_hash',args->>'code_hash','confirm_binding',true));
    IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION USING ERRCODE='P0001'; END IF;
    owner:=source.owner_subject_id;
   EXCEPTION WHEN SQLSTATE 'P0001' THEN RETURN result;
   END;
  END IF;
  UPDATE nku_identity_pilot_v1.agent_devices SET owner_subject_id=owner WHERE challenge_hash=d.challenge_hash;
  UPDATE nku_identity_pilot_v1.native_browser_intakes SET authorized=true WHERE challenge_hash=d.challenge_hash;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','browser_authorized','has_space',true,'created',created,'workspace_ref',ws));
 END IF;
 IF op='detach' THEN
  result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',args->>'session_hash'));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
  IF s.csrf_hash<>args->>'csrf_hash' OR s.owner_subject_id IS DISTINCT FROM owner THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  UPDATE nku_identity_pilot_v1.native_browser_intakes SET authorized=false WHERE challenge_hash=d.challenge_hash;
  IF n.child_session_hash IS NOT NULL AND n.child_session_hash<>s.token_hash THEN
   UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0 WHERE token_hash=n.child_session_hash;
  END IF;
  RETURN jsonb_build_object('ok',true,'data','{}'::jsonb);
 END IF;
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash' AND expires_at>now_s;
 IF s.token_hash IS NOT NULL AND owner IS NOT NULL AND (s.owner_subject_id<>owner OR s.workspace_ref<>ws)
  THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF s.token_hash IS NOT NULL AND n.authorized AND owner IS NOT NULL THEN
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status',CASE WHEN op='claim' THEN 'already_logged_in' ELSE 'bound' END,
   'has_space',true,'created',false,'workspace_ref',ws));
 END IF;
 IF op='state' OR NOT n.authorized OR owner IS NULL THEN
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status',CASE WHEN n.authorized THEN 'browser_authorized'
   WHEN owner IS NOT NULL THEN 'existing_space' WHEN d.owner_subject_id IS NOT NULL THEN 'legacy_authorization_required'
   ELSE 'first_use_confirmation' END,'has_space',owner IS NOT NULL,'created',false,'workspace_ref',ws));
 END IF;
 -- A valid logged-in browser without native consent is not replaced. Requiring
 -- explicit new consent above also prevents an immediate logout resurrection.
 IF n.child_session_hash IS NOT NULL AND EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions
  WHERE token_hash=n.child_session_hash AND expires_at>now_s) THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 IF (SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions WHERE owner_subject_id=owner AND expires_at>now_s)>=20
  THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
 INSERT INTO nku_identity_pilot_v1.browser_sessions(token_hash,owner_subject_id,workspace_ref,csrf_hash,expires_at,native_device_challenge_hash)
  VALUES(args->>'token_hash',owner,ws,args->>'csrf_hash',253370736000,d.challenge_hash);
 UPDATE nku_identity_pilot_v1.native_browser_intakes SET child_session_hash=args->>'token_hash' WHERE challenge_hash=d.challenge_hash;
 RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','bound','has_space',true,'created',false,
  'workspace_ref',ws,'expires_epoch',253370736000));
END $$;
REVOKE ALL ON FUNCTION public.nku_native_browser_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_native_browser_v1_rpc(text,jsonb) TO service_role;

-- Native proof cannot bypass an explicit native logout using legacy resume.
ALTER FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) RENAME TO nku_identity_pilot_v1_before_native_browser_rpc;
CREATE FUNCTION public.nku_identity_pilot_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='visitor_begin' AND EXISTS(SELECT 1 FROM nku_identity_pilot_v1.native_browser_intakes
  WHERE challenge_hash=args->>'challenge_hash') THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 RETURN public.nku_identity_pilot_v1_before_native_browser_rpc(op,args);
END $$;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_before_native_browser_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) TO service_role;
COMMIT;
