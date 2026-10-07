-- ADDITIVE competition-only compatibility. Run once, after explicit approval.
-- Does NOT replace the original 15 tables/RPC or its S256 OAuth state.
BEGIN;
CREATE SCHEMA nku_competition_oauth_v1;
REVOKE ALL ON SCHEMA nku_competition_oauth_v1 FROM PUBLIC,anon,authenticated;
CREATE TABLE nku_competition_oauth_v1.requests (
  transaction_hash text PRIMARY KEY CHECK(transaction_hash ~ '^[0-9a-f]{64}$'),
  source_session_hash text NOT NULL REFERENCES nku_identity_pilot_v1.browser_sessions ON DELETE CASCADE,
  audience text NOT NULL CHECK(audience ~ '^[A-Za-z0-9._:-]{8,128}$'),
  redirect_uri text NOT NULL CHECK(redirect_uri='https://coze.nankai.edu.cn/product/llm/info/oauth'),
  state text NOT NULL CHECK(length(state) BETWEEN 8 AND 256 AND state ~ '^[A-Za-z0-9._~-]+$'),
  expires_at bigint NOT NULL, grant_expires_at bigint NOT NULL,
  decision text CHECK(decision IN ('allow','deny'))
);
CREATE TABLE nku_competition_oauth_v1.codes (
  code_hash text PRIMARY KEY CHECK(code_hash ~ '^[0-9a-f]{64}$'),
  transaction_hash text NOT NULL UNIQUE REFERENCES nku_competition_oauth_v1.requests ON DELETE CASCADE,
  expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_competition_oauth_v1.grants (
  token_hash text PRIMARY KEY CHECK(token_hash ~ '^[0-9a-f]{64}$'),
  source_session_hash text NOT NULL REFERENCES nku_identity_pilot_v1.browser_sessions ON DELETE CASCADE,
  audience text NOT NULL, expires_at bigint NOT NULL
);
ALTER TABLE nku_competition_oauth_v1.requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_competition_oauth_v1.codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_competition_oauth_v1.grants ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_competition_oauth_v1 FROM PUBLIC,anon,authenticated;
CREATE FUNCTION public.nku_competition_oauth_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
  claims jsonb;
  expected text[];
  result jsonb;
  s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
  q nku_competition_oauth_v1.requests%ROWTYPE;
  c nku_competition_oauth_v1.codes%ROWTYPE;
  g nku_competition_oauth_v1.grants%ROWTYPE;
BEGIN
  claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
  IF claims->>'role' IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>4096 THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  expected:=CASE op
    WHEN 'probe' THEN ARRAY[]::text[]
    WHEN 'authorize_start' THEN ARRAY['session_hash','transaction_hash','audience','redirect_uri','state']
    WHEN 'authorize_approve' THEN ARRAY['session_hash','transaction_hash','decision','code_hash']
    WHEN 'exchange' THEN ARRAY['code_hash','audience','redirect_uri','token_hash']
    WHEN 'records' THEN ARRAY['grant_hash','audience']
    WHEN 'revoke' THEN ARRAY['token_hash','audience'] ELSE NULL END;
  IF expected IS NULL OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected)
    OR EXISTS(SELECT 1 FROM unnest(expected) k WHERE NOT args ? k OR jsonb_typeof(args->k) IS DISTINCT FROM 'string') THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF op='probe' THEN RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','competition-oauth-v1')); END IF;
  IF EXISTS(SELECT 1 FROM jsonb_each_text(args) e WHERE e.key LIKE '%hash' AND e.value !~ '^[0-9a-f]{64}$') THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF op='revoke' THEN
    DELETE FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'token_hash' AND audience=args->>'audience';
    RETURN jsonb_build_object('ok',true,'data','{}'::jsonb);
  END IF;
  IF op IN ('authorize_start','authorize_approve') THEN
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
  ELSIF op='exchange' THEN
    SELECT * INTO c FROM nku_competition_oauth_v1.codes WHERE code_hash=args->>'code_hash';
    SELECT * INTO q FROM nku_competition_oauth_v1.requests WHERE transaction_hash=c.transaction_hash;
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=q.source_session_hash;
  ELSE
    SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash' AND audience=args->>'audience';
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash;
  END IF;
  IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  -- Match the old owner lock order, so logout and reads do not deadlock.
  PERFORM pg_advisory_xact_lock(hashtextextended(s.owner_subject_id,604022002));
  now_s:=floor(extract(epoch FROM clock_timestamp()));
  result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
  IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RETURN result; END IF;
  IF op='authorize_start' THEN
    IF args->>'audience' !~ '^[A-Za-z0-9._:-]{8,128}$' OR length(args->>'state') NOT BETWEEN 8 AND 256
      OR args->>'state' !~ '^[A-Za-z0-9._~-]+$'
      OR args->>'redirect_uri'<>'https://coze.nankai.edu.cn/product/llm/info/oauth' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    DELETE FROM nku_competition_oauth_v1.requests WHERE expires_at<=now_s;
    IF (SELECT count(*) FROM nku_competition_oauth_v1.requests WHERE source_session_hash=s.token_hash)>=10 THEN
      RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED');
    END IF;
    INSERT INTO nku_competition_oauth_v1.requests VALUES(args->>'transaction_hash',s.token_hash,args->>'audience',
      args->>'redirect_uri',args->>'state',least(now_s+120,s.expires_at),least(now_s+600,s.expires_at),NULL);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('scopes',jsonb_build_array('demo:read')));
  ELSIF op='authorize_approve' THEN
    SELECT * INTO q FROM nku_competition_oauth_v1.requests WHERE transaction_hash=args->>'transaction_hash'
      AND source_session_hash=s.token_hash AND decision IS NULL AND expires_at>now_s FOR UPDATE;
    IF q.transaction_hash IS NULL OR args->>'decision' NOT IN ('allow','deny') THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
    UPDATE nku_competition_oauth_v1.requests SET decision=args->>'decision' WHERE transaction_hash=q.transaction_hash;
    IF args->>'decision'='allow' THEN
      INSERT INTO nku_competition_oauth_v1.codes VALUES(args->>'code_hash',q.transaction_hash,q.expires_at,NULL);
    END IF;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('redirect_uri',q.redirect_uri,'state',q.state));
  ELSIF op='exchange' THEN
    SELECT * INTO c FROM nku_competition_oauth_v1.codes WHERE code_hash=args->>'code_hash' FOR UPDATE;
    IF c.code_hash IS NULL OR c.used_at IS NOT NULL OR c.expires_at<=now_s OR q.decision IS DISTINCT FROM 'allow'
      OR q.audience IS DISTINCT FROM args->>'audience' OR q.redirect_uri IS DISTINCT FROM args->>'redirect_uri'
      OR q.grant_expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
    UPDATE nku_competition_oauth_v1.codes SET used_at=now_s WHERE code_hash=c.code_hash;
    INSERT INTO nku_competition_oauth_v1.grants VALUES(args->>'token_hash',s.token_hash,q.audience,q.grant_expires_at);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('expires_epoch',q.grant_expires_at,'scopes',jsonb_build_array('demo:read')));
  ELSE
    SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
      AND audience=args->>'audience' AND expires_at>now_s FOR UPDATE;
    IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
    RETURN public.nku_identity_pilot_v1_rpc('records',jsonb_build_object('session_hash',s.token_hash));
  END IF;
END;
$$;
REVOKE ALL ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) TO service_role;
COMMIT;
