-- New isolated schema. Does not alter MCP005, Tasks003 or public content.
-- Server-only RPC; fictional fixtures only. Never load raw passwords/tokens.
BEGIN;
CREATE SCHEMA nku_identity_pilot_v1;
REVOKE ALL ON SCHEMA nku_identity_pilot_v1 FROM PUBLIC, anon, authenticated;
CREATE TABLE nku_identity_pilot_v1.approved_subjects (subject_id text PRIMARY KEY);
CREATE TABLE nku_identity_pilot_v1.workspaces (
  workspace_ref text PRIMARY KEY, owner_subject_id text NOT NULL,
  fixture_set_id text NOT NULL CHECK (fixture_set_id='demo-v1'), expires_at bigint NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.owner_workspaces (
  subject_id text PRIMARY KEY, workspace_ref text NOT NULL UNIQUE REFERENCES nku_identity_pilot_v1.workspaces
);
CREATE TABLE nku_identity_pilot_v1.browser_sessions (
  token_hash text PRIMARY KEY, owner_subject_id text NOT NULL,
  workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
  csrf_hash text NOT NULL, expires_at bigint NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.fixtures (
  payload_hash text PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('task','schedule')), payload jsonb NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.drafts (
  draft_id text PRIMARY KEY, workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
  payload_hash text NOT NULL REFERENCES nku_identity_pilot_v1.fixtures,
  kind text NOT NULL CHECK(kind IN ('task','schedule')), revision integer NOT NULL DEFAULT 1,
  status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','committed')), expires_at bigint NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.confirmations (
  confirmation_hash text PRIMARY KEY, draft_id text NOT NULL REFERENCES nku_identity_pilot_v1.drafts,
  revision integer NOT NULL, payload_hash text NOT NULL, expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_identity_pilot_v1.tasks (
  task_id text PRIMARY KEY, draft_id text NOT NULL UNIQUE REFERENCES nku_identity_pilot_v1.drafts,
  confirmed_at bigint NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.schedules (
  schedule_id text PRIMARY KEY, workspace_ref text NOT NULL UNIQUE REFERENCES nku_identity_pilot_v1.workspaces,
  payload_hash text NOT NULL REFERENCES nku_identity_pilot_v1.fixtures,
  revision integer NOT NULL, confirmed_at bigint NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.idempotency (
  owner_subject_id text NOT NULL, operation text NOT NULL, key text NOT NULL,
  request_hash text NOT NULL, response jsonb NOT NULL,
  PRIMARY KEY(owner_subject_id,operation,key)
);
CREATE TABLE nku_identity_pilot_v1.import_tickets (
  ticket_hash text PRIMARY KEY, source_session_hash text NOT NULL,
  workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
  expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_identity_pilot_v1.oauth_requests (
  transaction_hash text PRIMARY KEY, source_session_hash text NOT NULL,
  audience text NOT NULL, redirect_uri text NOT NULL, scopes jsonb NOT NULL,
  challenge text NOT NULL, state text NOT NULL, expires_at bigint NOT NULL,
  grant_expires_at bigint NOT NULL, decision text CHECK(decision IN ('allow','deny'))
);
CREATE TABLE nku_identity_pilot_v1.oauth_codes (
  code_hash text PRIMARY KEY, transaction_hash text NOT NULL UNIQUE REFERENCES nku_identity_pilot_v1.oauth_requests ON DELETE CASCADE,
  expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_identity_pilot_v1.oauth_grants (
  token_hash text PRIMARY KEY, source_session_hash text NOT NULL,
  audience text NOT NULL, scopes jsonb NOT NULL, expires_at bigint NOT NULL
);
CREATE TABLE nku_identity_pilot_v1.rate_limits (
  bucket_hash text NOT NULL, window_start bigint NOT NULL, attempts integer NOT NULL,
  PRIMARY KEY(bucket_hash,window_start)
);
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='nku_identity_pilot_v1' LOOP
    EXECUTE format('ALTER TABLE nku_identity_pilot_v1.%I ENABLE ROW LEVEL SECURITY',t);
  END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_identity_pilot_v1 FROM PUBLIC, anon, authenticated;

CREATE FUNCTION nku_identity_pilot_v1.err(status integer, code text) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path='' AS $$
  SELECT jsonb_build_object('ok',false,'status',status,'code',code);
$$;
REVOKE ALL ON FUNCTION nku_identity_pilot_v1.err(integer,text) FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.nku_identity_pilot_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  now_s bigint := floor(extract(epoch FROM clock_timestamp()));
  claims jsonb;
  s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
  w nku_identity_pilot_v1.workspaces%ROWTYPE;
  d nku_identity_pilot_v1.drafts%ROWTYPE;
  c nku_identity_pilot_v1.confirmations%ROWTYPE;
  g nku_identity_pilot_v1.oauth_grants%ROWTYPE;
  q nku_identity_pilot_v1.oauth_requests%ROWTYPE;
  code nku_identity_pilot_v1.oauth_codes%ROWTYPE;
  ticket nku_identity_pilot_v1.import_tickets%ROWTYPE;
  idem nku_identity_pilot_v1.idempotency%ROWTYPE;
  sc nku_identity_pilot_v1.schedules%ROWTYPE;
  v_kind text;
  result jsonb;
  notice jsonb;
  schedule_json jsonb;
  tasks_json jsonb;
  hash_value text;
  owner text;
  principal_kind text := coalesce(args->>'principal_kind','browser');
  is_write boolean;
  attempt_count integer;
  limit_value integer;
BEGIN
  claims := coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
  IF claims->>'role' IS DISTINCT FROM 'service_role' THEN
    RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>32768 THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF op='probe' THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','identity-pilot-v1'));
  END IF;
  IF op='rate_limit' THEN
    IF coalesce(args->>'bucket_hash','') !~ '^[0-9a-f]{64}$' OR coalesce(args->>'limit','') !~ '^[0-9]{1,3}$' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    limit_value:=(args->>'limit')::integer;
    IF limit_value NOT BETWEEN 1 AND 120 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
    DELETE FROM nku_identity_pilot_v1.rate_limits WHERE window_start<now_s-120;
    INSERT INTO nku_identity_pilot_v1.rate_limits VALUES(args->>'bucket_hash',(now_s/60)*60,1)
      ON CONFLICT(bucket_hash,window_start) DO UPDATE SET attempts=nku_identity_pilot_v1.rate_limits.attempts+1
      RETURNING attempts INTO attempt_count;
    IF attempt_count>limit_value THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('allowed',true));
  END IF;
  IF op='configure_subjects' THEN
    -- Server startup only, never browser/model selected. Exactly the approved
    -- two ordinary users; only environment-namespaced digests cross this API.
    IF jsonb_typeof(args->'subjects') IS DISTINCT FROM 'array' OR jsonb_array_length(args->'subjects')<>2
      OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(args->'subjects') x WHERE x !~ '^cloudbase_pilot_[0-9a-f]{64}$')
      OR (SELECT count(DISTINCT x) FROM jsonb_array_elements_text(args->'subjects') x)<>2 THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    PERFORM pg_advisory_xact_lock(604022001);
    DELETE FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id NOT IN
      (SELECT jsonb_array_elements_text(args->'subjects'));
    INSERT INTO nku_identity_pilot_v1.approved_subjects SELECT jsonb_array_elements_text(args->'subjects') ON CONFLICT DO NOTHING;
    -- Restoring a removed user later must not resurrect an old active grant.
    DELETE FROM nku_identity_pilot_v1.browser_sessions WHERE owner_subject_id NOT IN
      (SELECT subject_id FROM nku_identity_pilot_v1.approved_subjects);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('configured',true));
  END IF;
  IF op='login' THEN
    owner:=args->>'subject_id';
    IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=owner) THEN
      RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
    END IF;
    IF coalesce(args->>'token_hash','') !~ '^[0-9a-f]{64}$' OR coalesce(args->>'csrf_hash','') !~ '^[0-9a-f]{64}$'
      OR coalesce(args->>'workspace_ref','') !~ '^pilot_workspace_[A-Za-z0-9_-]{24}$' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022002));
    SELECT ws.* INTO w FROM nku_identity_pilot_v1.owner_workspaces ow
      JOIN nku_identity_pilot_v1.workspaces ws ON ws.workspace_ref=ow.workspace_ref
      WHERE ow.subject_id=owner AND ws.owner_subject_id=owner AND ws.expires_at>now_s;
    IF NOT FOUND THEN
      INSERT INTO nku_identity_pilot_v1.workspaces VALUES(args->>'workspace_ref',owner,'demo-v1',now_s+86400) RETURNING * INTO w;
      INSERT INTO nku_identity_pilot_v1.owner_workspaces VALUES(owner,w.workspace_ref)
        ON CONFLICT(subject_id) DO UPDATE SET workspace_ref=excluded.workspace_ref;
    END IF;
    DELETE FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'previous_session_hash' AND owner_subject_id=owner;
    INSERT INTO nku_identity_pilot_v1.browser_sessions VALUES(args->>'token_hash',owner,w.workspace_ref,args->>'csrf_hash',now_s+900);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('workspace_ref',w.workspace_ref,'expires_epoch',now_s+900));
  END IF;
  IF op='oauth_exchange' THEN
    SELECT * INTO code FROM nku_identity_pilot_v1.oauth_codes WHERE code_hash=args->>'code_hash' FOR UPDATE;
    SELECT * INTO q FROM nku_identity_pilot_v1.oauth_requests WHERE transaction_hash=code.transaction_hash;
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=q.source_session_hash AND expires_at>now_s;
    SELECT * INTO w FROM nku_identity_pilot_v1.workspaces WHERE workspace_ref=s.workspace_ref AND owner_subject_id=s.owner_subject_id AND expires_at>now_s;
    IF code.code_hash IS NULL OR code.used_at IS NOT NULL OR code.expires_at<=now_s OR q.decision IS DISTINCT FROM 'allow'
      OR q.audience IS DISTINCT FROM args->>'audience' OR q.redirect_uri IS DISTINCT FROM args->>'redirect_uri'
      OR q.challenge IS DISTINCT FROM args->>'challenge' OR q.grant_expires_at<=now_s
      OR s.token_hash IS NULL OR w.workspace_ref IS NULL OR NOT EXISTS
        (SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=s.owner_subject_id) THEN
      RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
    END IF;
    IF coalesce(args->>'token_hash','') !~ '^[0-9a-f]{64}$' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
    UPDATE nku_identity_pilot_v1.oauth_codes SET used_at=now_s WHERE code_hash=code.code_hash;
    INSERT INTO nku_identity_pilot_v1.oauth_grants VALUES(args->>'token_hash',s.token_hash,q.audience,q.scopes,q.grant_expires_at);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('expires_epoch',q.grant_expires_at,'scopes',q.scopes));
  END IF;
  IF op='oauth_revoke' THEN
    DELETE FROM nku_identity_pilot_v1.oauth_grants WHERE token_hash=args->>'token_hash' AND audience=args->>'audience';
    RETURN jsonb_build_object('ok',true,'data','{}'::jsonb);
  END IF;
  IF principal_kind='agent' THEN
    SELECT * INTO g FROM nku_identity_pilot_v1.oauth_grants WHERE token_hash=args->>'grant_hash'
      AND audience=args->>'audience' AND expires_at>now_s;
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash AND expires_at>now_s;
    IF g.token_hash IS NULL OR NOT(g.scopes ? 'demo:read') OR op NOT IN ('records','create_draft')
      OR (op='create_draft' AND (NOT(g.scopes ? 'demo:draft') OR args->>'kind' IS DISTINCT FROM 'task')) THEN
      RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
    END IF;
  ELSIF principal_kind='import_ticket' THEN
    SELECT * INTO ticket FROM nku_identity_pilot_v1.import_tickets WHERE ticket_hash=args->>'ticket_hash' AND expires_at>now_s;
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=ticket.source_session_hash AND expires_at>now_s;
    IF ticket.ticket_hash IS NULL OR op<>'create_draft' OR args->>'kind' IS DISTINCT FROM 'schedule' THEN
      RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
    END IF;
  ELSIF principal_kind='browser' THEN
    SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash' AND expires_at>now_s;
  ELSE RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  IF s.token_hash IS NULL OR NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=s.owner_subject_id) THEN
    RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(s.owner_subject_id,604022002));
  now_s:=floor(extract(epoch FROM clock_timestamp()));
  -- Recheck after waiting for another owner's operation (e.g. logout).
  IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=s.token_hash AND expires_at>now_s)
    OR NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=s.owner_subject_id) THEN
    RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
  IF principal_kind='agent' AND NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.oauth_grants WHERE token_hash=g.token_hash AND expires_at>now_s) THEN
    RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED');
  END IF;
  IF principal_kind='import_ticket' THEN
    SELECT * INTO ticket FROM nku_identity_pilot_v1.import_tickets WHERE ticket_hash=args->>'ticket_hash' AND expires_at>now_s;
    IF ticket.ticket_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  END IF;
  SELECT * INTO w FROM nku_identity_pilot_v1.workspaces WHERE workspace_ref=s.workspace_ref AND owner_subject_id=s.owner_subject_id AND expires_at>now_s;
  IF w.workspace_ref IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF op NOT IN ('logout','get_workspace','records','list_tasks','current_schedule','get_task','get_draft',
    'create_draft','confirm','commit','import_ticket','authorize_start','authorize_approve') THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  is_write:=op IN ('logout','create_draft','confirm','commit','import_ticket');
  IF principal_kind='browser' AND is_write AND s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN
    RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
  END IF;
  IF args ? 'workspace_ref' AND args->>'workspace_ref' IS DISTINCT FROM w.workspace_ref THEN
    RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND');
  END IF;
  IF op='logout' THEN
    DELETE FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=s.token_hash;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('logged_out',true));
  ELSIF op='get_workspace' THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('workspace_ref',w.workspace_ref));
  ELSIF op='authorize_start' THEN
    IF coalesce(args->>'transaction_hash','') !~ '^[0-9a-f]{64}$' OR coalesce(args->>'challenge','') !~ '^[A-Za-z0-9_-]{43}$'
      OR length(coalesce(args->>'state','')) NOT BETWEEN 16 AND 256 OR coalesce(args->>'state','') !~ '^[A-Za-z0-9._~-]+$'
      OR jsonb_typeof(args->'scopes') IS DISTINCT FROM 'array'
      OR args->'scopes' NOT IN ('["demo:read"]'::jsonb,'["demo:draft","demo:read"]'::jsonb)
      OR coalesce(args->>'audience','') !~ '^[A-Za-z0-9._:-]{8,128}$' OR coalesce(args->>'redirect_uri','') !~ '^https://' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    DELETE FROM nku_identity_pilot_v1.oauth_requests WHERE expires_at<=now_s;
    IF (SELECT count(*) FROM nku_identity_pilot_v1.oauth_requests WHERE source_session_hash=s.token_hash)>=10 THEN
      RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED');
    END IF;
    INSERT INTO nku_identity_pilot_v1.oauth_requests VALUES(args->>'transaction_hash',s.token_hash,args->>'audience',args->>'redirect_uri',
      args->'scopes',args->>'challenge',args->>'state',least(now_s+120,s.expires_at),least(now_s+600,s.expires_at),NULL);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('scopes',args->'scopes'));
  ELSIF op='authorize_approve' THEN
    SELECT * INTO q FROM nku_identity_pilot_v1.oauth_requests WHERE transaction_hash=args->>'transaction_hash'
      AND source_session_hash=s.token_hash AND expires_at>now_s AND decision IS NULL FOR UPDATE;
    IF q.transaction_hash IS NULL OR coalesce(args->>'decision','') NOT IN ('allow','deny') THEN
      RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
    END IF;
    IF args->>'decision'='allow' AND coalesce(args->>'code_hash','') !~ '^[0-9a-f]{64}$' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    UPDATE nku_identity_pilot_v1.oauth_requests SET decision=args->>'decision' WHERE transaction_hash=q.transaction_hash;
    IF args->>'decision'='allow' THEN
      INSERT INTO nku_identity_pilot_v1.oauth_codes VALUES(args->>'code_hash',q.transaction_hash,q.expires_at,NULL);
    END IF;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('redirect_uri',q.redirect_uri,'state',q.state));
  END IF;
  IF op IN ('records','current_schedule','list_tasks','get_task') THEN
    SELECT * INTO sc FROM nku_identity_pilot_v1.schedules WHERE workspace_ref=w.workspace_ref;
    IF sc.schedule_id IS NOT NULL THEN
      SELECT jsonb_build_object('schedule_id',sc.schedule_id,'workspace_ref',w.workspace_ref,'revision',sc.revision,
        'timetable',f.payload,'confirmed_epoch',sc.confirmed_at) INTO schedule_json FROM nku_identity_pilot_v1.fixtures f WHERE f.payload_hash=sc.payload_hash;
    END IF;
    SELECT coalesce(jsonb_agg(jsonb_build_object('task_id',t.task_id,'workspace_ref',w.workspace_ref,'revision',1,
      'notice',f.payload,'confirmed_epoch',t.confirmed_at) ORDER BY t.confirmed_at DESC,t.task_id),'[]'::jsonb)
      INTO tasks_json FROM nku_identity_pilot_v1.tasks t JOIN nku_identity_pilot_v1.drafts ds ON ds.draft_id=t.draft_id
      JOIN nku_identity_pilot_v1.fixtures f ON f.payload_hash=ds.payload_hash WHERE ds.workspace_ref=w.workspace_ref
      AND (op<>'get_task' OR t.task_id=args->>'task_id');
    IF op='records' THEN result:=jsonb_build_object('schedule',schedule_json,'tasks',tasks_json,'dataset_kind','demo','personal_uploads',false);
    ELSIF op='current_schedule' THEN
      IF schedule_json IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
      result:=schedule_json;
    ELSIF op='get_task' THEN
      IF jsonb_array_length(tasks_json)=0 THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
      result:=tasks_json->0;
    ELSE result:=tasks_json;
    END IF;
    RETURN jsonb_build_object('ok',true,'data',result);
  END IF;
  IF op IN ('get_draft','confirm','commit') THEN
    IF op='commit' THEN
      SELECT * INTO c FROM nku_identity_pilot_v1.confirmations WHERE confirmation_hash=args->>'confirmation_hash';
      SELECT * INTO d FROM nku_identity_pilot_v1.drafts WHERE draft_id=c.draft_id AND workspace_ref=w.workspace_ref;
    ELSE
      SELECT * INTO d FROM nku_identity_pilot_v1.drafts WHERE draft_id=args->>'draft_id' AND workspace_ref=w.workspace_ref;
    END IF;
    IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
    IF d.expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
    SELECT payload INTO notice FROM nku_identity_pilot_v1.fixtures WHERE payload_hash=d.payload_hash;
    IF op='get_draft' THEN
      RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('draft_id',d.draft_id,'kind',d.kind,'workspace_ref',w.workspace_ref,
        'revision',d.revision,'payload',notice,'payload_hash',d.payload_hash,'status',d.status,'expires_epoch',d.expires_at));
    END IF;
  END IF;
  IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$' OR coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$' THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  -- Separate task/schedule commit domains prevent a cross-kind replay hit.
  v_kind:=coalesce(args->>'kind','');
  SELECT * INTO idem FROM nku_identity_pilot_v1.idempotency WHERE owner_subject_id=s.owner_subject_id
    AND operation=op||':'||v_kind AND key=args->>'key';
  IF FOUND THEN
    IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    RETURN jsonb_build_object('ok',true,'data',idem.response);
  END IF;
  IF op='import_ticket' THEN
    IF args->>'purpose' IS DISTINCT FROM 'schedule_import' OR coalesce(args->>'ticket_hash','') !~ '^[0-9a-f]{64}$' THEN
      RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
    END IF;
    INSERT INTO nku_identity_pilot_v1.import_tickets VALUES(args->>'ticket_hash',s.token_hash,w.workspace_ref,least(now_s+600,s.expires_at),NULL);
    result:=jsonb_build_object('ticket_id',args->>'ticket_id','workspace_ref',w.workspace_ref,'purpose','schedule_import','expires_epoch',least(now_s+600,s.expires_at));
  ELSIF op='create_draft' THEN
    IF v_kind NOT IN ('task','schedule') THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
    SELECT payload INTO notice FROM nku_identity_pilot_v1.fixtures WHERE payload_hash=args->>'payload_hash' AND fixtures.kind=v_kind;
    IF NOT FOUND THEN RETURN nku_identity_pilot_v1.err(403,'DEMO_ONLY'); END IF;
    IF principal_kind='import_ticket' AND ticket.used_at IS NOT NULL THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
    IF (SELECT count(*) FROM nku_identity_pilot_v1.drafts WHERE workspace_ref=w.workspace_ref)>=100 THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
    INSERT INTO nku_identity_pilot_v1.drafts(draft_id,workspace_ref,payload_hash,kind,expires_at)
      VALUES(args->>'draft_id',w.workspace_ref,args->>'payload_hash',v_kind,w.expires_at);
    IF principal_kind='import_ticket' THEN UPDATE nku_identity_pilot_v1.import_tickets SET used_at=now_s WHERE ticket_hash=ticket.ticket_hash; END IF;
    result:=jsonb_build_object('draft_id',args->>'draft_id','kind',v_kind,'workspace_ref',w.workspace_ref,'revision',1,'payload_hash',args->>'payload_hash',
      'status','draft','expires_epoch',w.expires_at);
  ELSE
    IF principal_kind<>'browser' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
    IF d.status<>'draft' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    IF d.kind='task' AND coalesce(jsonb_array_length(notice->'needs_confirmation'),1)>0 THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
    IF op='confirm' THEN
      IF args->>'revision' IS DISTINCT FROM d.revision::text OR args->>'payload_hash' IS DISTINCT FROM d.payload_hash THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
      INSERT INTO nku_identity_pilot_v1.confirmations VALUES(args->>'confirmation_hash',d.draft_id,d.revision,d.payload_hash,least(now_s+600,s.expires_at),NULL);
      result:=jsonb_build_object('confirmation_id',args->>'confirmation_id','draft_id',d.draft_id,'revision',d.revision,'payload_hash',d.payload_hash,
        'expires_epoch',least(now_s+600,s.expires_at));
    ELSE
      IF op<>'commit' OR v_kind<>d.kind OR c.revision<>d.revision OR c.payload_hash<>d.payload_hash THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
      IF c.expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
      IF c.used_at IS NOT NULL THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
      IF v_kind='task' THEN
        INSERT INTO nku_identity_pilot_v1.tasks VALUES(args->>'resource_id',d.draft_id,now_s);
        result:=jsonb_build_object('task_id',args->>'resource_id','revision',1);
      ELSE
        INSERT INTO nku_identity_pilot_v1.schedules VALUES(args->>'resource_id',w.workspace_ref,d.payload_hash,1,now_s)
          ON CONFLICT(workspace_ref) DO UPDATE SET payload_hash=excluded.payload_hash,revision=nku_identity_pilot_v1.schedules.revision+1,confirmed_at=now_s
          RETURNING * INTO sc;
        result:=jsonb_build_object('schedule_id',sc.schedule_id,'revision',sc.revision);
      END IF;
      UPDATE nku_identity_pilot_v1.confirmations SET used_at=now_s WHERE confirmation_hash=c.confirmation_hash;
      UPDATE nku_identity_pilot_v1.drafts SET status='committed' WHERE draft_id=d.draft_id;
    END IF;
  END IF;
  INSERT INTO nku_identity_pilot_v1.idempotency VALUES(s.owner_subject_id,op||':'||v_kind,args->>'key',args->>'request_hash',result);
  RETURN jsonb_build_object('ok',true,'data',result);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) TO service_role;
COMMIT;
