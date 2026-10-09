-- Device enrollment, inspired by Heartbeat Calendar, not GeniOS SSO.
-- LOCAL ACCEPTANCE ONLY until the browser adapter and deployment are accepted.
-- No new owner, workspace, OAuth scope, or extension of a source session.
BEGIN;
ALTER TABLE nku_identity_pilot_v1.browser_sessions
 ADD COLUMN device_source_session_hash text
 REFERENCES nku_identity_pilot_v1.browser_sessions(token_hash) ON DELETE CASCADE;
CREATE TABLE nku_identity_pilot_v1.device_enrollments (
 challenge_hash text PRIMARY KEY, code_hash text NOT NULL UNIQUE,
 expires_at bigint NOT NULL, used_at bigint,
 source_session_hash text REFERENCES nku_identity_pilot_v1.browser_sessions(token_hash) ON DELETE CASCADE,
 receipt_hash text UNIQUE, receipt_expires_at bigint, approved_at bigint
);
ALTER TABLE nku_identity_pilot_v1.device_enrollments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.device_enrollments FROM PUBLIC,anon,authenticated,service_role;

-- Shortening a source session also shortens every bound child; never extend it.
CREATE FUNCTION nku_identity_pilot_v1.shorten_device_sessions() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
 IF NEW.expires_at<OLD.expires_at THEN
  UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=least(expires_at,NEW.expires_at)
   WHERE device_source_session_hash=NEW.token_hash;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION nku_identity_pilot_v1.shorten_device_sessions() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER shorten_device_sessions AFTER UPDATE OF expires_at ON nku_identity_pilot_v1.browser_sessions
 FOR EACH ROW EXECUTE FUNCTION nku_identity_pilot_v1.shorten_device_sessions();

CREATE FUNCTION public.nku_browser_device_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
 expected text[]; e nku_identity_pilot_v1.device_enrollments%ROWTYPE;
 s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 w nku_identity_pilot_v1.workspaces%ROWTYPE; result jsonb; k text;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','browser-device-v1')); END IF;
 expected:=CASE op
  WHEN 'start' THEN ARRAY['challenge_hash','code_hash']
  WHEN 'review' THEN ARRAY['session_hash','csrf_hash','code_hash','receipt_hash']
  WHEN 'approve' THEN ARRAY['session_hash','csrf_hash','code_hash','receipt_hash','confirm_device']
  WHEN 'claim' THEN ARRAY['challenge_hash','token_hash','csrf_hash'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>4096
  OR expected IS NULL OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected)
  OR NOT args ?& expected THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 FOREACH k IN ARRAY expected LOOP
  IF k<>'confirm_device' AND (jsonb_typeof(args->k) IS DISTINCT FROM 'string'
   OR coalesce(args->>k,'') !~ '^[0-9a-f]{64}$') THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END LOOP;
 IF op='approve' AND args->'confirm_device' IS DISTINCT FROM 'true'::jsonb THEN
  RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
 IF op='start' THEN
  -- The HTTP adapter must additionally rate-limit per caller. No identity here.
  DELETE FROM nku_identity_pilot_v1.device_enrollments WHERE expires_at<=now_s;
  IF (SELECT count(*) FROM nku_identity_pilot_v1.device_enrollments)>=1000 THEN
   RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
  INSERT INTO nku_identity_pilot_v1.device_enrollments(challenge_hash,code_hash,expires_at)
   VALUES(args->>'challenge_hash',args->>'code_hash',now_s+300) ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('expires_epoch',now_s+300));
 END IF;
 IF op IN ('review','approve') THEN
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
  IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  IF s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' OR s.device_source_session_hash IS NOT NULL THEN
   RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  -- A paired device cannot mint an unbounded chain of additional devices.
  SELECT * INTO e FROM nku_identity_pilot_v1.device_enrollments WHERE code_hash=args->>'code_hash' FOR UPDATE;
  IF e.challenge_hash IS NULL OR e.used_at IS NOT NULL OR e.expires_at<=now_s
   OR e.approved_at IS NOT NULL THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  IF op='review' THEN
   IF e.source_session_hash IS NOT NULL AND e.receipt_expires_at>now_s THEN
    RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   UPDATE nku_identity_pilot_v1.device_enrollments SET source_session_hash=s.token_hash,
    receipt_hash=args->>'receipt_hash',receipt_expires_at=least(now_s+60,e.expires_at)
    WHERE challenge_hash=e.challenge_hash;
   RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('confirmation_required',true,
    'expires_epoch',least(now_s+60,e.expires_at)));
  END IF;
  IF e.source_session_hash IS DISTINCT FROM s.token_hash OR e.receipt_hash IS DISTINCT FROM args->>'receipt_hash'
   OR e.receipt_expires_at IS NULL OR e.receipt_expires_at<=now_s THEN
   RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
  UPDATE nku_identity_pilot_v1.device_enrollments SET approved_at=now_s WHERE challenge_hash=e.challenge_hash;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('approved',true));
 END IF;
 -- Only the initiating browser's independent, HttpOnly challenge may claim.
 -- A display code or review receipt is NEVER a login credential.
 SELECT * INTO e FROM nku_identity_pilot_v1.device_enrollments WHERE challenge_hash=args->>'challenge_hash' FOR UPDATE;
 IF e.challenge_hash IS NULL OR e.used_at IS NOT NULL OR e.expires_at<=now_s THEN
  RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
 IF e.approved_at IS NULL THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','pending')); END IF;
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=e.source_session_hash;
 IF s.token_hash IS NULL OR s.device_source_session_hash IS NOT NULL THEN
  RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
 IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(s.owner_subject_id,604022002));
 IF (SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions WHERE device_source_session_hash=s.token_hash)>=20 THEN
  RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
 SELECT * INTO w FROM nku_identity_pilot_v1.workspaces WHERE workspace_ref=s.workspace_ref AND owner_subject_id=s.owner_subject_id;
 INSERT INTO nku_identity_pilot_v1.browser_sessions
  (token_hash,owner_subject_id,workspace_ref,csrf_hash,expires_at,device_source_session_hash)
  VALUES(args->>'token_hash',s.owner_subject_id,s.workspace_ref,args->>'csrf_hash',least(s.expires_at,w.expires_at),s.token_hash)
  ON CONFLICT DO NOTHING;
 IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 UPDATE nku_identity_pilot_v1.device_enrollments SET used_at=now_s WHERE challenge_hash=e.challenge_hash;
 RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','bound',
  'workspace_ref',s.workspace_ref,'expires_epoch',least(s.expires_at,w.expires_at)));
END $$;
REVOKE ALL ON FUNCTION public.nku_browser_device_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_browser_device_v1_rpc(text,jsonb) TO service_role;
COMMIT;
