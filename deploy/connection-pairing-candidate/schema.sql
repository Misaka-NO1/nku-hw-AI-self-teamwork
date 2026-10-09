-- OFFLINE CANDIDATE. Not executed in CloudBase. Creates NEW objects only.
-- Strict /oauth/* PKCE schema and RPC remain unchanged. Enabled defaults false.
BEGIN;
CREATE SCHEMA nku_connection_pairing_candidate_v1;
REVOKE ALL ON SCHEMA nku_connection_pairing_candidate_v1 FROM PUBLIC,anon,authenticated;
CREATE TABLE nku_connection_pairing_candidate_v1.settings (
  singleton boolean PRIMARY KEY CHECK(singleton), audience text NOT NULL,
  enabled boolean NOT NULL DEFAULT false
);
INSERT INTO nku_connection_pairing_candidate_v1.settings VALUES(true,'offline-connection-pairing-test',false);
CREATE TABLE nku_connection_pairing_candidate_v1.codes (
  code_hash text PRIMARY KEY, audience text NOT NULL,
  expires_at bigint NOT NULL, consumed_at bigint
);
CREATE TABLE nku_connection_pairing_candidate_v1.connections (
  token_hash text PRIMARY KEY, user_code_hash text NOT NULL UNIQUE,
  audience text NOT NULL, expires_at bigint NOT NULL, pairing_expires_at bigint NOT NULL,
  owner_subject_id text REFERENCES nku_identity_pilot_v1.approved_subjects ON DELETE CASCADE,
  source_session_hash text REFERENCES nku_identity_pilot_v1.browser_sessions ON DELETE CASCADE,
  active_expires_at bigint, revoked_at bigint,
  CHECK ((owner_subject_id IS NULL AND source_session_hash IS NULL AND active_expires_at IS NULL)
      OR (owner_subject_id IS NOT NULL AND source_session_hash IS NOT NULL AND active_expires_at IS NOT NULL))
);
CREATE TABLE nku_connection_pairing_candidate_v1.reviews (
  receipt_hash text PRIMARY KEY,
  token_hash text NOT NULL REFERENCES nku_connection_pairing_candidate_v1.connections ON DELETE CASCADE,
  source_session_hash text NOT NULL REFERENCES nku_identity_pilot_v1.browser_sessions ON DELETE CASCADE,
  owner_subject_id text NOT NULL REFERENCES nku_identity_pilot_v1.approved_subjects ON DELETE CASCADE,
  expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_connection_pairing_candidate_v1.review_limits (
  owner_subject_id text PRIMARY KEY, started_at bigint NOT NULL, attempts integer NOT NULL
);
CREATE TABLE nku_connection_pairing_candidate_v1.bootstrap_limits (
  audience text NOT NULL, window_start bigint NOT NULL, attempts integer NOT NULL,
  PRIMARY KEY(audience,window_start)
);
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='nku_connection_pairing_candidate_v1' LOOP
    EXECUTE format('ALTER TABLE nku_connection_pairing_candidate_v1.%I ENABLE ROW LEVEL SECURITY',t);
  END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_connection_pairing_candidate_v1 FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.nku_connection_pairing_candidate_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  now_s bigint := floor(extract(epoch FROM clock_timestamp()));
  claims jsonb;
  cfg nku_connection_pairing_candidate_v1.settings%ROWTYPE;
  bc nku_connection_pairing_candidate_v1.codes%ROWTYPE;
  cn nku_connection_pairing_candidate_v1.connections%ROWTYPE;
  rv nku_connection_pairing_candidate_v1.reviews%ROWTYPE;
  sl nku_identity_pilot_v1.browser_sessions%ROWTYPE;
  limit_row nku_connection_pairing_candidate_v1.review_limits%ROWTYPE;
  count_value integer;
  allowed_keys text[];
BEGIN
  claims := coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
  IF claims->>'role' IS DISTINCT FROM 'service_role' THEN
    RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>8192 THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF op='probe' AND args='{}'::jsonb THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','connection-pairing-candidate-v1'));
  END IF;
  IF op='configure' THEN
    IF (SELECT count(*) FROM jsonb_object_keys(args))<>2 OR NOT args ?& ARRAY['audience','enabled']
      OR jsonb_typeof(args->'audience') IS DISTINCT FROM 'string'
      OR coalesce(args->>'audience','') !~ '^[A-Za-z0-9._:-]{8,128}$'
      OR jsonb_typeof(args->'enabled') IS DISTINCT FROM 'boolean' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    UPDATE nku_connection_pairing_candidate_v1.settings SET audience=args->>'audience',enabled=(args->>'enabled')::boolean WHERE singleton;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('configured',true));
  END IF;
  SELECT * INTO cfg FROM nku_connection_pairing_candidate_v1.settings WHERE singleton;
  IF NOT FOUND OR NOT cfg.enabled THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  allowed_keys := CASE op
    WHEN 'bootstrap' THEN ARRAY['audience','code_hash']
    WHEN 'exchange' THEN ARRAY['audience','code_hash','token_hash','user_code_hash']
    WHEN 'review' THEN ARRAY['session_hash','csrf_hash','user_code_hash','receipt_hash']
    WHEN 'approve' THEN ARRAY['session_hash','csrf_hash','receipt_hash','user_code_hash','confirm_same_agent','confirm_read']
    WHEN 'records' THEN ARRAY['audience','token_hash']
    WHEN 'revoke' THEN ARRAY['audience','token_hash']
    ELSE NULL END;
  IF allowed_keys IS NULL OR NOT args ?& allowed_keys
    OR (SELECT count(*) FROM jsonb_object_keys(args))<>array_length(allowed_keys,1) THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_each(args) x WHERE x.key LIKE '%hash' AND
      (jsonb_typeof(x.value) IS DISTINCT FROM 'string' OR (x.value#>>'{}') !~ '^[0-9a-f]{64}$')) THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF args ? 'audience' AND args->>'audience' IS DISTINCT FROM cfg.audience THEN
    RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;

  IF op='bootstrap' THEN
    INSERT INTO nku_connection_pairing_candidate_v1.bootstrap_limits VALUES(cfg.audience,(now_s/60)*60,1)
      ON CONFLICT(audience,window_start) DO UPDATE SET attempts=nku_connection_pairing_candidate_v1.bootstrap_limits.attempts+1 RETURNING attempts INTO count_value;
    IF count_value>20 OR (SELECT count(*) FROM nku_connection_pairing_candidate_v1.codes WHERE consumed_at IS NULL AND expires_at>now_s)>=100 THEN
      RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED');
    END IF;
    INSERT INTO nku_connection_pairing_candidate_v1.codes VALUES(args->>'code_hash',cfg.audience,now_s+90,NULL) ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('expires_epoch',now_s+90));
  END IF;

  IF op='exchange' THEN
    SELECT * INTO bc FROM nku_connection_pairing_candidate_v1.codes WHERE code_hash=args->>'code_hash' FOR UPDATE;
    IF NOT FOUND OR bc.audience<>cfg.audience OR bc.expires_at<=now_s OR bc.consumed_at IS NOT NULL THEN
      RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
    END IF;
    INSERT INTO nku_connection_pairing_candidate_v1.connections(token_hash,user_code_hash,audience,expires_at,pairing_expires_at)
      VALUES(args->>'token_hash',args->>'user_code_hash',cfg.audience,now_s+600,now_s+300) ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    UPDATE nku_connection_pairing_candidate_v1.codes SET consumed_at=now_s WHERE code_hash=bc.code_hash;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','pairing_required','expires_epoch',now_s+600,'pairing_expires_epoch',now_s+300));
  END IF;

  IF op IN ('review','approve') THEN
    SELECT s.* INTO sl FROM nku_identity_pilot_v1.browser_sessions s
      JOIN nku_identity_pilot_v1.approved_subjects a ON a.subject_id=s.owner_subject_id
      JOIN nku_identity_pilot_v1.workspaces w ON w.workspace_ref=s.workspace_ref AND w.owner_subject_id=s.owner_subject_id
      WHERE s.token_hash=args->>'session_hash' AND s.expires_at>now_s AND w.expires_at>now_s;
    IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
    IF sl.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(sl.owner_subject_id,604022002));
    -- Revalidate after the owner lock: concurrent logout/expiry cannot grant.
    IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=sl.token_hash AND expires_at>now_s) THEN
      RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
    END IF;
  END IF;

  IF op='review' THEN
    SELECT * INTO limit_row FROM nku_connection_pairing_candidate_v1.review_limits WHERE owner_subject_id=sl.owner_subject_id FOR UPDATE;
    IF FOUND AND limit_row.started_at+300>now_s AND limit_row.attempts>=5 THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
    IF NOT FOUND OR limit_row.started_at+300<=now_s THEN
      INSERT INTO nku_connection_pairing_candidate_v1.review_limits VALUES(sl.owner_subject_id,now_s,1)
        ON CONFLICT(owner_subject_id) DO UPDATE SET started_at=excluded.started_at,attempts=1;
    ELSE
      UPDATE nku_connection_pairing_candidate_v1.review_limits SET attempts=attempts+1 WHERE owner_subject_id=sl.owner_subject_id;
    END IF;
    SELECT * INTO cn FROM nku_connection_pairing_candidate_v1.connections WHERE user_code_hash=args->>'user_code_hash';
    IF NOT FOUND OR cn.owner_subject_id IS NOT NULL OR cn.revoked_at IS NOT NULL OR cn.pairing_expires_at<=now_s OR cn.audience<>cfg.audience THEN
      RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND');
    END IF;
    INSERT INTO nku_connection_pairing_candidate_v1.reviews VALUES(args->>'receipt_hash',cn.token_hash,sl.token_hash,sl.owner_subject_id,least(now_s+60,sl.expires_at,cn.pairing_expires_at),NULL) ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('permission','read_own_fixed_demo_records','expires_epoch',least(now_s+60,sl.expires_at,cn.pairing_expires_at)));
  END IF;

  IF op='approve' THEN
    IF args->'confirm_same_agent' IS DISTINCT FROM 'true'::jsonb OR args->'confirm_read' IS DISTINCT FROM 'true'::jsonb THEN
      RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED');
    END IF;
    SELECT * INTO rv FROM nku_connection_pairing_candidate_v1.reviews WHERE receipt_hash=args->>'receipt_hash' FOR UPDATE;
    IF NOT FOUND OR rv.used_at IS NOT NULL OR rv.expires_at<=now_s OR rv.source_session_hash<>sl.token_hash OR rv.owner_subject_id<>sl.owner_subject_id THEN
      RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
    END IF;
    SELECT * INTO cn FROM nku_connection_pairing_candidate_v1.connections WHERE token_hash=rv.token_hash FOR UPDATE;
    IF NOT FOUND OR cn.owner_subject_id IS NOT NULL OR cn.revoked_at IS NOT NULL OR cn.pairing_expires_at<=now_s
      OR cn.user_code_hash<>args->>'user_code_hash' OR cn.audience<>cfg.audience THEN
      RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION');
    END IF;
    UPDATE nku_connection_pairing_candidate_v1.connections SET owner_subject_id=sl.owner_subject_id,source_session_hash=sl.token_hash,
      active_expires_at=least(cn.expires_at,now_s+600,sl.expires_at) WHERE token_hash=cn.token_hash;
    UPDATE nku_connection_pairing_candidate_v1.reviews SET used_at=now_s WHERE receipt_hash=rv.receipt_hash;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','paired','permission','read_own_fixed_demo_records','expires_epoch',least(cn.expires_at,now_s+600,sl.expires_at)));
  END IF;

  SELECT * INTO cn FROM nku_connection_pairing_candidate_v1.connections WHERE token_hash=args->>'token_hash';
  IF NOT FOUND OR cn.audience<>cfg.audience OR cn.revoked_at IS NOT NULL OR cn.expires_at<=now_s THEN
    RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
  IF op='revoke' THEN
    UPDATE nku_connection_pairing_candidate_v1.connections SET revoked_at=now_s WHERE token_hash=cn.token_hash;
    RETURN jsonb_build_object('ok',true,'data','{}'::jsonb);
  END IF;
  IF cn.owner_subject_id IS NULL THEN
    IF cn.pairing_expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('status','pairing_required','expires_epoch',cn.pairing_expires_at));
  END IF;
  IF cn.active_expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions s
    JOIN nku_identity_pilot_v1.approved_subjects a ON a.subject_id=s.owner_subject_id
    JOIN nku_identity_pilot_v1.workspaces w ON w.workspace_ref=s.workspace_ref AND w.owner_subject_id=s.owner_subject_id
    WHERE s.token_hash=cn.source_session_hash AND s.owner_subject_id=cn.owner_subject_id
      AND s.expires_at>now_s AND w.expires_at>now_s) THEN
    RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
  -- Internal source is the already-approved, immutable grant binding, NOT an
  -- externally supplied owner/workspace. Existing read RPC revalidates session.
  RETURN public.nku_identity_pilot_v1_rpc('records',jsonb_build_object('session_hash',cn.source_session_hash));
END;
$$;
REVOKE ALL ON FUNCTION public.nku_connection_pairing_candidate_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_connection_pairing_candidate_v1_rpc(text,jsonb) TO service_role;
COMMIT;
