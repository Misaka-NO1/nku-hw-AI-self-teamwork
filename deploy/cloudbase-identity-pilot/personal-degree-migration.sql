-- ADDITIVE personal curriculum-degree storage (module 6). Run once, after
-- schema.sql and competition-oauth-migration.sql, with explicit approval.
-- Does NOT replace, rename or wrap the original public.nku_identity_pilot_v1_rpc
-- or any other existing RPC/table; the two identity members are read only.
-- Owner is always derived from the verified browser session / verified grant,
-- never from a request-supplied owner, workspace or subject argument.
BEGIN;
-- Prerequisites are part of this migration's contract: the original identity
-- RPC and the competition grants must exist untouched.
DO $$ BEGIN
  IF to_regprocedure('public.nku_identity_pilot_v1_rpc(text,jsonb)') IS NULL
    OR to_regclass('nku_identity_pilot_v1.browser_sessions') IS NULL
    OR to_regclass('nku_competition_oauth_v1.grants') IS NULL THEN
    RAISE EXCEPTION 'personal-degree migration requires the applied identity and competition-oauth migrations';
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS nku_personal_degree_v1;
REVOKE ALL ON SCHEMA nku_personal_degree_v1 FROM PUBLIC,anon,authenticated,service_role;

-- Draft of one confirmed degree-table observation. workspace_ref is derived
-- from the session (browser) or from the verified records result (Agent).
CREATE TABLE IF NOT EXISTS nku_personal_degree_v1.degree_drafts (
  draft_id text PRIMARY KEY CHECK(draft_id ~ '^draft_[A-Za-z0-9_-]{24}$'),
  workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
  observation jsonb NOT NULL,
  report jsonb NOT NULL,
  payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
  report_hash text NOT NULL CHECK(report_hash ~ '^[0-9a-f]{64}$'),
  revision integer NOT NULL DEFAULT 1,
  base_revision integer NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','committed')),
  expires_at bigint NOT NULL
);
-- One-use confirmation receipts. Several receipts may exist for one draft, but
-- only one commit consumes the draft and advances the workspace snapshot.
CREATE TABLE IF NOT EXISTS nku_personal_degree_v1.degree_confirmations (
  confirmation_hash text PRIMARY KEY CHECK(confirmation_hash ~ '^[0-9a-f]{64}$'),
  draft_id text NOT NULL REFERENCES nku_personal_degree_v1.degree_drafts,
  revision integer NOT NULL,
  payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
  report_hash text NOT NULL CHECK(report_hash ~ '^[0-9a-f]{64}$'),
  share_with_agent boolean NOT NULL,
  expires_at bigint NOT NULL,
  used_at bigint
);
-- Confirmed current snapshot per workspace. observation and report are stored
-- separately; share_with_agent records the user's explicit consent for the
-- Agent read path. There is no separate revoke operation: consent is captured
-- per snapshot at confirm/commit, and a new snapshot is needed to change it.
CREATE TABLE IF NOT EXISTS nku_personal_degree_v1.degree_snapshots (
  workspace_ref text PRIMARY KEY REFERENCES nku_identity_pilot_v1.workspaces,
  degree_id text NOT NULL,
  observation jsonb NOT NULL,
  report jsonb NOT NULL,
  payload_hash text NOT NULL,
  report_hash text NOT NULL,
  revision integer NOT NULL CHECK(revision>0),
  share_with_agent boolean NOT NULL,
  confirmed_at bigint NOT NULL
);
-- Separate from the original idempotency table, whose response contract belongs
-- to the fixture draft/confirmation tables.
CREATE TABLE IF NOT EXISTS nku_personal_degree_v1.degree_idempotency (
  owner_subject_id text NOT NULL,
  operation text NOT NULL,
  key text NOT NULL,
  request_hash text NOT NULL,
  response jsonb NOT NULL,
  PRIMARY KEY(owner_subject_id,operation,key)
);
ALTER TABLE nku_personal_degree_v1.degree_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_personal_degree_v1.degree_confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_personal_degree_v1.degree_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_personal_degree_v1.degree_idempotency ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_personal_degree_v1
  FROM PUBLIC,anon,authenticated,service_role;

-- Server-side lookup used by the Agent path only. Reads no request-supplied
-- owner; the workspace comes from the caller's already verified principal.
CREATE FUNCTION nku_personal_degree_v1.snapshot(workspace text) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
  SELECT jsonb_build_object('degree_id',s.degree_id,'workspace_ref',s.workspace_ref,
    'revision',s.revision,'observation',s.observation,'report',s.report,
    'confirmed_epoch',s.confirmed_at)
  FROM nku_personal_degree_v1.degree_snapshots s
  WHERE s.workspace_ref=workspace AND s.share_with_agent;
$$;
REVOKE ALL ON FUNCTION nku_personal_degree_v1.snapshot(text)
  FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.nku_personal_degree_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
 now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
 claims jsonb;
 s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 w nku_identity_pilot_v1.workspaces%ROWTYPE;
 d nku_personal_degree_v1.degree_drafts%ROWTYPE;
 lc nku_personal_degree_v1.degree_confirmations%ROWTYPE;
 sd nku_personal_degree_v1.degree_snapshots%ROWTYPE;
 idem nku_personal_degree_v1.degree_idempotency%ROWTYPE;
 observation jsonb; report jsonb;
 expected text[]; auth_keys text[]; descriptor jsonb; verified jsonb; data jsonb;
 owner text; current_revision integer:=0; own_workspace text;
BEGIN
 claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
 IF claims->>'role' IS DISTINCT FROM 'service_role' THEN
  RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
 END IF;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>1048576 THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 IF op='probe' AND args='{}'::jsonb THEN
  RETURN jsonb_build_object('ok',true,'data',
    jsonb_build_object('schema_version','personal-degree-v1'));
 END IF;
 expected:=CASE op
  WHEN 'records' THEN ARRAY[]::text[]
  WHEN 'current' THEN ARRAY[]::text[]
  WHEN 'get_draft' THEN ARRAY['draft_id']
  WHEN 'draft' THEN ARRAY['observation','report','payload_hash','report_hash','draft_id','key','request_hash']
  WHEN 'confirm' THEN ARRAY['draft_id','revision','payload_hash','report_hash','share_with_agent',
    'confirmation_id','confirmation_hash','key','request_hash']
  WHEN 'commit' THEN ARRAY['confirmation_hash','resource_id','share_with_agent','key','request_hash']
  ELSE NULL END;
 auth_keys:=CASE args->>'principal_kind'
  WHEN 'browser' THEN ARRAY['principal_kind','session_hash','csrf_hash']
  WHEN 'agent' THEN ARRAY['principal_kind','grant_mode','grant_hash','audience'] ELSE NULL END;
 -- Strict key set: an owner/workspace_ref/subject argument can never be accepted.
 IF expected IS NULL OR auth_keys IS NULL
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected||auth_keys)
  OR NOT args ?& (expected||auth_keys) THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 -- Every hex named field is a string sha256; share flags are real JSON booleans.
 IF EXISTS(SELECT 1 FROM jsonb_each(args) e WHERE e.key LIKE '%hash'
   AND jsonb_typeof(e.value) IS DISTINCT FROM 'string') THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 IF EXISTS(SELECT 1 FROM jsonb_each(args) e WHERE e.key LIKE '%hash'
   AND (e.value #>> '{}') !~ '^[0-9a-f]{64}$') THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 IF args ? 'share_with_agent' AND jsonb_typeof(args->'share_with_agent') IS DISTINCT FROM 'boolean' THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 IF args->>'principal_kind'='browser' THEN
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions bs
    WHERE bs.token_hash=args->>'session_hash' AND bs.expires_at>now_s;
  -- Reads additionally require a well-formed CSRF field; writes must match it.
  IF s.token_hash IS NOT NULL AND op NOT IN ('records','current','get_draft')
    AND s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN
   RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  descriptor:=jsonb_build_object('principal_kind','browser');
 ELSIF args->>'principal_kind'='agent' THEN
  -- Agent is read-only for its own owner: no draft/confirm/commit path exists.
  IF op<>'records' OR args->>'grant_mode' NOT IN ('strict','competition') THEN
   RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  descriptor:=jsonb_build_object('principal_kind','agent','grant_hash',args->>'grant_hash',
    'audience',args->>'audience');
  IF args->>'grant_mode'='competition' THEN
   SELECT bs.* INTO s FROM nku_identity_pilot_v1.browser_sessions bs
    JOIN nku_competition_oauth_v1.grants g ON g.source_session_hash=bs.token_hash
    WHERE g.token_hash=args->>'grant_hash' AND g.audience=args->>'audience' AND g.expires_at>now_s;
  ELSE
   SELECT bs.* INTO s FROM nku_identity_pilot_v1.browser_sessions bs
    JOIN nku_identity_pilot_v1.oauth_grants g ON g.source_session_hash=bs.token_hash
    WHERE g.token_hash=args->>'grant_hash' AND g.audience=args->>'audience' AND g.expires_at>now_s;
  END IF;
 ELSE
  RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
 END IF;
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 owner:=s.owner_subject_id;
 PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022002));
 now_s:=floor(extract(epoch FROM clock_timestamp()));
 -- Recheck after waiting for another owner's operation (for example logout).
 IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions bs
   WHERE bs.token_hash=s.token_hash AND bs.expires_at>now_s) THEN
  RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
 END IF;
 -- Existing authorization: get_workspace revalidates session, approval,
 -- owner/workspace binding and expiry for browser principals.
 verified:=public.nku_identity_pilot_v1_rpc('get_workspace',
   jsonb_build_object('session_hash',s.token_hash));
 IF verified->>'ok' IS DISTINCT FROM 'true' THEN RETURN verified; END IF;
 SELECT * INTO w FROM nku_identity_pilot_v1.workspaces ws
   WHERE ws.workspace_ref=verified->'data'->>'workspace_ref'
    AND ws.owner_subject_id=s.owner_subject_id AND ws.expires_at>now_s;
 IF w.workspace_ref IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 own_workspace:=w.workspace_ref;
 IF args->>'principal_kind'='agent' THEN
  -- Existing effective authorization RPC resolves the principal and the
  -- workspace; workspace_ref is never taken from this request.
  IF args->>'grant_mode'='competition' THEN
   verified:=public.nku_competition_oauth_v1_rpc('records',
     jsonb_build_object('grant_hash',args->>'grant_hash','audience',args->>'audience'));
   IF verified->>'ok' IS DISTINCT FROM 'true' THEN RETURN verified; END IF;
   own_workspace:=coalesce(verified->'data'->'schedule'->>'workspace_ref',
     (verified->'data'->'tasks'->0)->>'workspace_ref',w.workspace_ref);
  ELSE
   -- Strict identity grants keep their original demo:read scope and are
   -- verified by the original identity RPC, not re-implemented here.
   verified:=public.nku_identity_pilot_v1_rpc('records',
     jsonb_build_object('principal_kind','agent','grant_hash',args->>'grant_hash',
       'audience',args->>'audience'));
   IF verified->>'ok' IS DISTINCT FROM 'true' THEN RETURN verified; END IF;
   own_workspace:=coalesce(verified->'data'->'schedule'->>'workspace_ref',
     (verified->'data'->'tasks'->0)->>'workspace_ref',w.workspace_ref);
  END IF;
  IF own_workspace IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF own_workspace IS DISTINCT FROM w.workspace_ref THEN
   RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND');
  END IF;
  IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions bs
    WHERE bs.token_hash=s.token_hash AND bs.expires_at>floor(extract(epoch FROM clock_timestamp()))) THEN
   RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
 END IF;
 now_s:=floor(extract(epoch FROM clock_timestamp()));
 SELECT * INTO sd FROM nku_personal_degree_v1.degree_snapshots snap
  WHERE snap.workspace_ref=own_workspace;
 IF sd.workspace_ref IS NOT NULL THEN current_revision:=sd.revision; END IF;
 IF op IN ('records','current') THEN
  IF args->>'principal_kind'='agent' THEN
   -- Agent reads only an explicitly shared confirmed snapshot; otherwise it is
   -- indistinguishable from "nothing imported" and no demo record is returned.
   IF sd.workspace_ref IS NULL OR NOT sd.share_with_agent THEN
    RETURN jsonb_build_object('ok',true,'data','null'::jsonb);
   END IF;
   RETURN jsonb_build_object('ok',true,'data',nku_personal_degree_v1.snapshot(own_workspace));
  END IF;
  -- Browser current/records: the caller's own confirmed snapshot or null.
  -- Never the fixed public demo record.
  IF sd.workspace_ref IS NULL THEN RETURN jsonb_build_object('ok',true,'data','null'::jsonb); END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('degree_id',sd.degree_id,
    'workspace_ref',sd.workspace_ref,'revision',sd.revision,'observation',sd.observation,
    'report',sd.report,'confirmed_epoch',sd.confirmed_at));
 END IF;
 IF op='get_draft' THEN
  SELECT * INTO d FROM nku_personal_degree_v1.degree_drafts dd
    WHERE dd.draft_id=args->>'draft_id' AND dd.workspace_ref=own_workspace FOR UPDATE;
  IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF d.expires_at<=now_s AND d.status<>'committed' THEN
   RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED');
  END IF;
  -- Owner-isolated: a foreign draft is reported as absent.
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('draft_id',d.draft_id,
    'kind','degree','workspace_ref',d.workspace_ref,'revision',d.revision,'payload',d.observation,
    'report',d.report,'payload_hash',d.payload_hash,'report_hash',d.report_hash,
    'status',d.status,'expires_epoch',d.expires_at));
 END IF;
 -- Writes below are browser-only; Agent principals were refused above.
 IF args->>'principal_kind'<>'browser' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$'
  OR coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$' THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 IF op='draft' THEN
  observation:=args->'observation'; report:=args->'report';
  IF jsonb_typeof(observation) IS DISTINCT FROM 'object'
    OR octet_length(observation::text)>1048576 THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF observation->>'kind' IS DISTINCT FROM 'degree-table-observation' THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF (SELECT count(*) FROM jsonb_object_keys(observation))<>4
    OR NOT observation ?& ARRAY['kind','source','headers','rows'] THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  -- source: exactly the canonical page, coverage and adapter flags of the
  -- independent degree observation contract. No identity fields exist here.
  IF jsonb_typeof(observation->'source') IS DISTINCT FROM 'object'
    OR (SELECT count(*) FROM jsonb_object_keys(observation->'source'))<>4
    OR NOT observation->'source' ?& ARRAY['url','captured_at','coverage','adapter_verified']
    OR observation->'source'->>'url' IS DISTINCT FROM 'https://eamis.nankai.edu.cn/eams/myPlanCompl.action'
    OR observation->'source'->>'coverage' NOT IN ('partial','unknown')
    OR jsonb_typeof(observation->'source'->'adapter_verified') IS DISTINCT FROM 'boolean'
    OR observation->'source'->'adapter_verified' IS DISTINCT FROM 'false'::jsonb
    OR length(coalesce(observation->'source'->>'captured_at','')) NOT BETWEEN 10 AND 40 THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF jsonb_typeof(observation->'headers') IS DISTINCT FROM 'array'
    OR jsonb_array_length(observation->'headers') NOT BETWEEN 7 AND 8
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(observation->'headers') h
      WHERE jsonb_typeof(h) IS DISTINCT FROM 'string')
    OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(observation->'headers') h
      WHERE h NOT IN ('序号','课程序号','课程名称','要求学分','实修学分','成绩','是否通过','备注'))
    OR (SELECT count(DISTINCT h) FROM jsonb_array_elements_text(observation->'headers') h)<>jsonb_array_length(observation->'headers')
    OR NOT observation->'headers' @> '["课程序号","课程名称","要求学分","实修学分","成绩","是否通过","备注"]'::jsonb THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF jsonb_typeof(observation->'rows') IS DISTINCT FROM 'array'
    OR jsonb_array_length(observation->'rows') NOT BETWEEN 1 AND 2000 THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(observation->'rows') r
    WHERE jsonb_typeof(r) IS DISTINCT FROM 'object'
     OR (SELECT count(*) FROM jsonb_object_keys(r))<>2
     OR NOT r ?& ARRAY['cells','locator']
     OR jsonb_typeof(r->'cells') IS DISTINCT FROM 'array'
     OR jsonb_array_length(r->'cells')>64
     OR EXISTS(SELECT 1 FROM jsonb_array_elements(r->'cells') c
       WHERE jsonb_typeof(c) IS DISTINCT FROM 'string' OR length((c #>> '{}')::text)>4096)
     OR jsonb_typeof(r->'locator') IS DISTINCT FROM 'string'
     OR length(r->>'locator') NOT BETWEEN 1 AND 256) THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  -- report: the confirmed analysis derived from this observation. It must not
  -- be empty and must not claim a different page or adapter state.
  IF jsonb_typeof(report) IS DISTINCT FROM 'object'
    OR octet_length(report::text)>524288
    OR jsonb_typeof(report->'courses') IS DISTINCT FROM 'array'
    OR jsonb_typeof(report->'modules') IS DISTINCT FROM 'array'
    OR report->'source'->>'url' IS DISTINCT FROM observation->'source'->>'url'
    OR report->'source'->>'captured_at' IS DISTINCT FROM observation->'source'->>'captured_at'
    OR report->'source'->'adapter_verified' IS DISTINCT FROM 'false'::jsonb THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  -- The backend supplies the sha256 fingerprints; SQL only checks their format.
  IF coalesce(args->>'report_hash','') !~ '^[0-9a-f]{64}$'
    OR coalesce(args->>'payload_hash','') !~ '^[0-9a-f]{64}$'
    OR coalesce(args->>'draft_id','') !~ '^draft_[A-Za-z0-9_-]{24}$' THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  -- Idempotent replay first: a duplicate delivery of the same request must not
  -- create a second draft, and must keep working after later commits.
  SELECT * INTO idem FROM nku_personal_degree_v1.degree_idempotency i
    WHERE i.owner_subject_id=owner AND i.operation=op AND i.key=args->>'key';
  IF FOUND THEN
   IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN
    RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION');
   END IF;
   RETURN jsonb_build_object('ok',true,'data',idem.response);
  END IF;
  -- Conservatively refuse pages that carry identity text (student number,
  -- name, password or similar) rather than storing fabricated identity data.
  IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(observation->'headers') h
   WHERE h ~ '(学号|姓名|验证码|密码|身份证|考生号|学籍号|准考证|联系电话|手机号)') THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(observation->'rows') r,
    jsonb_array_elements_text(r->'cells') c
   WHERE c ~ '(学号|姓名)\s*[:：]|验证码|密码(?!学)|身份证|考生号|学籍号|准考证|联系电话|手机号') THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF (SELECT count(*) FROM nku_personal_degree_v1.degree_drafts dd
    WHERE dd.workspace_ref=own_workspace AND dd.status='draft' AND dd.expires_at>now_s)>=100 THEN
   RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED');
  END IF;
  -- The base revision is captured now; a later commit must match it.
  INSERT INTO nku_personal_degree_v1.degree_drafts(draft_id,workspace_ref,observation,report,
    payload_hash,report_hash,revision,base_revision,status,expires_at)
   VALUES(args->>'draft_id',own_workspace,observation,report,args->>'payload_hash',
    args->>'report_hash',1,current_revision,'draft',least(now_s+86400,w.expires_at))
   RETURNING * INTO d;
  data:=jsonb_build_object('draft_id',d.draft_id,'workspace_ref',d.workspace_ref,
    'revision',d.revision,'payload_hash',d.payload_hash,'report_hash',d.report_hash,
    'status',d.status,'expires_epoch',d.expires_at);
  INSERT INTO nku_personal_degree_v1.degree_idempotency VALUES(owner,op,args->>'key',args->>'request_hash',data);
  RETURN jsonb_build_object('ok',true,'data',data);
 END IF;
 -- Replay after receipt expiry/consumption still requires a live same-owner session.
 SELECT * INTO idem FROM nku_personal_degree_v1.degree_idempotency i
  WHERE i.owner_subject_id=owner AND i.operation=op AND i.key=args->>'key';
 IF FOUND THEN
  IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  RETURN jsonb_build_object('ok',true,'data',idem.response);
 END IF;
 -- Confirm and commit act on an existing receipt/draft of this owner.
 IF op='commit' THEN
  SELECT * INTO lc FROM nku_personal_degree_v1.degree_confirmations dc
    WHERE dc.confirmation_hash=args->>'confirmation_hash';
  IF lc.confirmation_hash IS NULL OR lc.expires_at<=now_s THEN
   RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED');
  END IF;
  SELECT * INTO d FROM nku_personal_degree_v1.degree_drafts dd
    WHERE dd.draft_id=lc.draft_id AND dd.workspace_ref=own_workspace FOR UPDATE;
  IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF d.expires_at<=now_s AND d.status<>'committed' THEN
   RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED');
  END IF;
  IF lc.revision<>d.revision OR lc.payload_hash<>d.payload_hash
    OR lc.report_hash<>d.report_hash OR lc.share_with_agent IS DISTINCT FROM true
    OR args->'share_with_agent' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION');
  END IF;
 ELSE
  SELECT * INTO d FROM nku_personal_degree_v1.degree_drafts dd
    WHERE dd.draft_id=args->>'draft_id' AND dd.workspace_ref=own_workspace FOR UPDATE;
  IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF d.expires_at<=now_s AND d.status<>'committed' THEN
   RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED');
  END IF;
 END IF;
 SELECT * INTO idem FROM nku_personal_degree_v1.degree_idempotency i
   WHERE i.owner_subject_id=owner AND i.operation=op AND i.key=args->>'key';
 IF FOUND THEN
  IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN
   RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION');
  END IF;
  -- A replay of an already committed request must not need a fresh receipt.
  RETURN jsonb_build_object('ok',true,'data',idem.response);
 END IF;
 IF op='confirm' THEN
  -- In the commit branch d is locked; in the confirm branch it was locked too.
  IF d.status<>'draft' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF current_revision<>d.base_revision THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  -- The user's explicit per-snapshot consent is required, not a default.
  IF args->'share_with_agent' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  IF args->>'revision' IS DISTINCT FROM d.revision::text
    OR args->>'payload_hash' IS DISTINCT FROM d.payload_hash
    OR args->>'report_hash' IS DISTINCT FROM d.report_hash THEN
   RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION');
  END IF;
  -- Several receipts may be issued for one draft; each is one-use.
  INSERT INTO nku_personal_degree_v1.degree_confirmations(confirmation_hash,draft_id,revision,
    payload_hash,report_hash,share_with_agent,expires_at,used_at)
   VALUES(args->>'confirmation_hash',d.draft_id,d.revision,d.payload_hash,d.report_hash,true,
    least(now_s+600,s.expires_at),NULL);
  data:=jsonb_build_object('confirmation_id',args->>'confirmation_id','draft_id',d.draft_id,
    'workspace_ref',own_workspace,'revision',d.revision,'payload_hash',d.payload_hash,
    'report_hash',d.report_hash,'share_with_agent',true,'expires_epoch',least(now_s+600,s.expires_at));
  INSERT INTO nku_personal_degree_v1.degree_idempotency VALUES(owner,op,args->>'key',args->>'request_hash',data);
  RETURN jsonb_build_object('ok',true,'data',data);
 END IF;
 IF op<>'commit' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF coalesce(args->>'resource_id','') !~ '^degree_[A-Za-z0-9_-]{24}$' THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
 END IF;
 -- Only one commit may consume a draft; every other receipt replays or fails.
 IF d.status<>'draft' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 IF lc.used_at IS NOT NULL THEN
  RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED');
 END IF;
 -- The draft's base revision must still be the workspace's current revision.
 IF current_revision<>d.base_revision THEN
  RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION');
 END IF;
 SELECT * INTO sd FROM nku_personal_degree_v1.degree_snapshots snap
  WHERE snap.workspace_ref=own_workspace FOR UPDATE;
 IF sd.workspace_ref IS NULL THEN
  INSERT INTO nku_personal_degree_v1.degree_snapshots(workspace_ref,degree_id,observation,report,
    payload_hash,report_hash,revision,share_with_agent,confirmed_at)
   VALUES(own_workspace,args->>'resource_id',d.observation,d.report,d.payload_hash,d.report_hash,
    current_revision+1,true,now_s) RETURNING * INTO sd;
 ELSE
  UPDATE nku_personal_degree_v1.degree_snapshots snap
   SET degree_id=args->>'resource_id',observation=d.observation,report=d.report,
    payload_hash=d.payload_hash,report_hash=d.report_hash,revision=current_revision+1,
    share_with_agent=true,confirmed_at=now_s
   WHERE snap.workspace_ref=own_workspace RETURNING * INTO sd;
 END IF;
 UPDATE nku_personal_degree_v1.degree_drafts SET status='committed' WHERE draft_id=d.draft_id;
 UPDATE nku_personal_degree_v1.degree_confirmations SET used_at=now_s
  WHERE confirmation_hash=lc.confirmation_hash;
 data:=jsonb_build_object('degree_id',sd.degree_id,'workspace_ref',sd.workspace_ref,
  'revision',sd.revision,'confirmed_epoch',sd.confirmed_at);
 INSERT INTO nku_personal_degree_v1.degree_idempotency VALUES(owner,op,args->>'key',args->>'request_hash',data);
 RETURN jsonb_build_object('ok',true,'data',data);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_personal_degree_v1_rpc(text,jsonb)
  FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_personal_degree_v1_rpc(text,jsonb) TO service_role;
COMMIT;
