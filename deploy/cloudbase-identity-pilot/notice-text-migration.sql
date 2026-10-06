-- Additive backend candidate; NOT executed online. Uses existing verified
-- identity/workspaces and the same owner lock; does not replace old RPC/tables.
BEGIN;
CREATE SCHEMA nku_notice_text_v1;
REVOKE ALL ON SCHEMA nku_notice_text_v1 FROM PUBLIC,anon,authenticated;
CREATE TABLE nku_notice_text_v1.drafts (
  draft_id text PRIMARY KEY, workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
  plan jsonb NOT NULL, payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
  revision integer NOT NULL DEFAULT 1, status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','committed')),
  expires_at bigint NOT NULL
);
CREATE TABLE nku_notice_text_v1.confirmations (
  confirmation_hash text PRIMARY KEY CHECK(confirmation_hash ~ '^[0-9a-f]{64}$'),
  draft_id text NOT NULL REFERENCES nku_notice_text_v1.drafts,
  revision integer NOT NULL, payload_hash text NOT NULL, expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_notice_text_v1.tasks (
  task_id text PRIMARY KEY, workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
  draft_id text NOT NULL UNIQUE REFERENCES nku_notice_text_v1.drafts,
  notice_id text NOT NULL, confirmed_at bigint NOT NULL, UNIQUE(workspace_ref,notice_id)
);
CREATE TABLE nku_notice_text_v1.idempotency (
  owner_subject_id text NOT NULL, operation text NOT NULL, key text NOT NULL,
  request_hash text NOT NULL, response jsonb NOT NULL,
  PRIMARY KEY(owner_subject_id,operation,key)
);
ALTER TABLE nku_notice_text_v1.drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_notice_text_v1.confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_notice_text_v1.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_notice_text_v1.idempotency ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_notice_text_v1 FROM PUBLIC,anon,authenticated;

CREATE FUNCTION nku_notice_text_v1.snapshot(session_hash text) RETURNS jsonb
LANGUAGE plpgsql SET search_path='' AS $$
DECLARE base jsonb; extra jsonb; combined jsonb; workspace text;
BEGIN
  base:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',session_hash));
  IF base->>'ok' IS DISTINCT FROM 'true' THEN RETURN base; END IF;
  workspace:=base->'data'->>'workspace_ref';
  base:=public.nku_identity_pilot_v1_rpc('records',jsonb_build_object('session_hash',session_hash));
  IF base->>'ok' IS DISTINCT FROM 'true' THEN RETURN base; END IF;
  -- Calculations need semantic fields, not the possibly long original text.
  SELECT coalesce(jsonb_agg(jsonb_build_object('task_id',t.task_id,'workspace_ref',workspace,'revision',d.revision,
    'confirmed_epoch',t.confirmed_at,'notice',jsonb_build_object('plan_version','notice-text-pilot-v1',
      'kind',d.plan->'kind','notice',d.plan->'notice'||jsonb_build_object('source_spans','[]'::jsonb,'materials','[]'::jsonb),
      'selected_slot',d.plan->'selected_slot')) ORDER BY t.task_id),'[]'::jsonb) INTO extra
    FROM nku_notice_text_v1.tasks t JOIN nku_notice_text_v1.drafts d ON d.draft_id=t.draft_id
    WHERE t.workspace_ref=workspace;
  combined:=base->'data'->'tasks'||extra;
  RETURN jsonb_build_object('ok',true,'data',base->'data'||jsonb_build_object('tasks',combined,
    'workspace_ref',workspace,'dataset_mode','fictional_notice_text',
    'records_revision',md5(jsonb_build_object('schedule',base->'data'->'schedule','tasks',combined)::text)));
END;
$$;
REVOKE ALL ON FUNCTION nku_notice_text_v1.snapshot(text) FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.nku_notice_text_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  now_s bigint:=floor(extract(epoch FROM clock_timestamp())); claims jsonb;
  s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
  w nku_identity_pilot_v1.workspaces%ROWTYPE;
  d nku_notice_text_v1.drafts%ROWTYPE; c nku_notice_text_v1.confirmations%ROWTYPE;
  idem nku_notice_text_v1.idempotency%ROWTYPE;
  expected text[]; auth_keys text[]; result jsonb; snapshot jsonb; records jsonb;
  session_token text; mode text; data jsonb; items jsonb; v_operation text;
  skip_count integer; page_size integer; total_count integer;
BEGIN
  claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
  IF claims->>'role' IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>524288 THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF op='probe' AND args='{}'::jsonb THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','notice-text-v1'));
  END IF;
  expected:=CASE op
    WHEN 'records' THEN ARRAY[]::text[]
    WHEN 'get_draft' THEN ARRAY['draft_id']
    WHEN 'get_confirmation' THEN ARRAY['confirmation_hash']
    WHEN 'get_task' THEN ARRAY['task_id']
    WHEN 'list_tasks' THEN ARRAY['offset','limit']
    WHEN 'lookup' THEN ARRAY['operation','key','request_hash']
    WHEN 'create' THEN ARRAY['plan','payload_hash','records_revision','draft_id','key','request_hash']
    WHEN 'update' THEN ARRAY['plan','payload_hash','records_revision','draft_id','revision','key','request_hash']
    WHEN 'confirm' THEN ARRAY['draft_id','revision','payload_hash','confirmation_id','confirmation_hash','records_revision','key','request_hash']
    WHEN 'commit' THEN ARRAY['confirmation_hash','resource_id','records_revision','key','request_hash'] ELSE NULL END;
  mode:=args->>'principal_kind';
  IF mode='browser' THEN auth_keys:=ARRAY['principal_kind','session_hash','csrf_hash'];
  ELSIF mode='agent' THEN auth_keys:=ARRAY['principal_kind','grant_mode','grant_hash','audience'];
  ELSE RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF expected IS NULL OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected||auth_keys)
    OR NOT args ?& (expected||auth_keys) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  IF mode='agent' AND op<>'records' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF EXISTS(SELECT 1 FROM jsonb_each(args) e WHERE e.key LIKE '%hash' AND
      (jsonb_typeof(e.value) IS DISTINCT FROM 'string' OR coalesce(args->>e.key,'') !~ '^[0-9a-f]{64}$')) THEN
    RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  IF mode='browser' THEN session_token:=args->>'session_hash';
  ELSIF args->>'grant_mode'='strict' THEN
    SELECT source_session_hash INTO session_token FROM nku_identity_pilot_v1.oauth_grants
      WHERE token_hash=args->>'grant_hash' AND audience=args->>'audience' AND expires_at>now_s AND scopes ? 'demo:read';
  ELSIF args->>'grant_mode'='competition' THEN
    SELECT source_session_hash INTO session_token FROM nku_competition_oauth_v1.grants
      WHERE token_hash=args->>'grant_hash' AND audience=args->>'audience' AND expires_at>now_s;
  ELSE RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=session_token;
  IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  -- Same lock as the old fixture RPC: schedule saves, new tasks and logout
  -- serialize together. Python's calculation uses the snapshot version below.
  PERFORM pg_advisory_xact_lock(hashtextextended(s.owner_subject_id,604022002));
  now_s:=floor(extract(epoch FROM clock_timestamp()));
  result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
  IF result->>'ok' IS DISTINCT FROM 'true' THEN RETURN result; END IF;
  SELECT * INTO w FROM nku_identity_pilot_v1.workspaces WHERE workspace_ref=result->'data'->>'workspace_ref';
  IF mode='agent' THEN
    IF args->>'grant_mode'='strict' AND NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.oauth_grants
      WHERE token_hash=args->>'grant_hash' AND audience=args->>'audience' AND expires_at>now_s AND scopes ? 'demo:read') THEN
      RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
    IF args->>'grant_mode'='competition' AND NOT EXISTS(SELECT 1 FROM nku_competition_oauth_v1.grants
      WHERE token_hash=args->>'grant_hash' AND audience=args->>'audience' AND expires_at>now_s) THEN
      RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
  END IF;
  IF op IN ('create','update','confirm','commit','lookup') AND s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN
    RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF op='records' THEN RETURN nku_notice_text_v1.snapshot(s.token_hash); END IF;
  IF op IN ('get_draft','update','confirm') THEN
    SELECT * INTO d FROM nku_notice_text_v1.drafts WHERE draft_id=args->>'draft_id' AND workspace_ref=w.workspace_ref;
    IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  ELSIF op IN ('get_confirmation','commit') THEN
    SELECT * INTO c FROM nku_notice_text_v1.confirmations WHERE confirmation_hash=args->>'confirmation_hash';
    SELECT * INTO d FROM nku_notice_text_v1.drafts WHERE draft_id=c.draft_id AND workspace_ref=w.workspace_ref;
    IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
    IF c.revision<>d.revision OR c.payload_hash<>d.payload_hash THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    IF d.status='draft' AND c.expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  END IF;
  IF d.draft_id IS NOT NULL AND d.expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  IF op IN ('get_draft','get_confirmation') THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('draft_id',d.draft_id,'workspace_ref',w.workspace_ref,
      'kind','task','revision',d.revision,'payload',d.plan,'payload_hash',d.payload_hash,'status',d.status,'expires_epoch',d.expires_at));
  END IF;
  IF op='get_task' THEN
    SELECT jsonb_build_object('task_id',t.task_id,'workspace_ref',w.workspace_ref,'revision',d2.revision,
      'notice',d2.plan,'confirmed_epoch',t.confirmed_at) INTO data FROM nku_notice_text_v1.tasks t
      JOIN nku_notice_text_v1.drafts d2 ON d2.draft_id=t.draft_id WHERE t.task_id=args->>'task_id' AND t.workspace_ref=w.workspace_ref;
    IF data IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
    RETURN jsonb_build_object('ok',true,'data',data);
  END IF;
  IF op='list_tasks' THEN
    IF jsonb_typeof(args->'offset') IS DISTINCT FROM 'number' OR jsonb_typeof(args->'limit') IS DISTINCT FROM 'number'
      OR coalesce(args->>'offset','') !~ '^[0-9]{1,3}$' OR coalesce(args->>'limit','') !~ '^[1-5]$' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
    skip_count:=(args->>'offset')::integer; page_size:=(args->>'limit')::integer;
    IF skip_count>100 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
    SELECT count(*) INTO total_count FROM nku_notice_text_v1.tasks WHERE workspace_ref=w.workspace_ref;
    SELECT coalesce(jsonb_agg(page.item),'[]'::jsonb) INTO items FROM (
      SELECT jsonb_build_object('task_id',t.task_id,'workspace_ref',w.workspace_ref,'revision',d2.revision,
        'notice',d2.plan,'confirmed_epoch',t.confirmed_at) item FROM nku_notice_text_v1.tasks t
      JOIN nku_notice_text_v1.drafts d2 ON d2.draft_id=t.draft_id WHERE t.workspace_ref=w.workspace_ref
      ORDER BY t.task_id OFFSET skip_count LIMIT page_size) page;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('items',items,'total',total_count,
      'next_offset',CASE WHEN skip_count+page_size<total_count THEN skip_count+page_size ELSE NULL END));
  END IF;
  IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  v_operation:=CASE WHEN op='lookup' THEN args->>'operation' ELSE op END;
  IF v_operation NOT IN ('create','update','confirm','commit') THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  SELECT * INTO idem FROM nku_notice_text_v1.idempotency WHERE owner_subject_id=s.owner_subject_id
    AND idempotency.operation=v_operation AND key=args->>'key';
  IF FOUND THEN
    IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    -- A fresh login after workspace expiry must not resurrect an old cached
    -- draft/receipt/result belonging to the previous workspace of this owner.
    IF idem.response ? 'workspace_ref' AND idem.response->>'workspace_ref' IS DISTINCT FROM w.workspace_ref THEN
      RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
    IF idem.response ? 'draft_id' AND NOT EXISTS(SELECT 1 FROM nku_notice_text_v1.drafts
      WHERE draft_id=idem.response->>'draft_id' AND workspace_ref=w.workspace_ref AND expires_at>now_s) THEN
      RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
    IF idem.response ? 'task_id' AND NOT EXISTS(SELECT 1 FROM nku_notice_text_v1.tasks
      WHERE task_id=idem.response->>'task_id' AND workspace_ref=w.workspace_ref) THEN
      RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
    IF v_operation='confirm' AND (idem.response->>'expires_epoch')::bigint<=now_s THEN
      RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
    RETURN jsonb_build_object('ok',true,'data',idem.response);
  END IF;
  IF op='lookup' THEN RETURN jsonb_build_object('ok',true,'data','null'::jsonb); END IF;
  IF d.draft_id IS NOT NULL AND d.status<>'draft' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  snapshot:=nku_notice_text_v1.snapshot(s.token_hash);
  IF snapshot->>'ok' IS DISTINCT FROM 'true' THEN RETURN snapshot; END IF;
  records:=snapshot->'data';
  IF records->>'records_revision' IS DISTINCT FROM args->>'records_revision' THEN
    RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF op IN ('create','update') THEN
    IF jsonb_typeof(args->'plan') IS DISTINCT FROM 'object' OR octet_length((args->'plan')::text)>262144
      OR args->'plan'->>'plan_version' IS DISTINCT FROM 'notice-text-pilot-v1'
      OR args->'plan'->'notice'->'needs_confirmation' IS DISTINCT FROM '[]'::jsonb
      OR args->'plan'->'user_confirmations'->'source_review' IS DISTINCT FROM 'true'::jsonb
      OR args->'plan'->'fictional_data_confirmed' IS DISTINCT FROM 'true'::jsonb
      OR args->'plan'->>'kind' NOT IN ('event_conflict','deadline_feasibility')
      OR coalesce(args->'plan'->'notice'->>'notice_id','')='' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
    IF EXISTS(SELECT 1 FROM nku_notice_text_v1.tasks WHERE workspace_ref=w.workspace_ref
      AND notice_id=args->'plan'->'notice'->>'notice_id') THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    IF op='create' THEN
      IF (SELECT count(*) FROM nku_notice_text_v1.drafts WHERE workspace_ref=w.workspace_ref)>=100 THEN
        RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
      INSERT INTO nku_notice_text_v1.drafts(draft_id,workspace_ref,plan,payload_hash,expires_at)
        VALUES(args->>'draft_id',w.workspace_ref,args->'plan',args->>'payload_hash',w.expires_at) RETURNING * INTO d;
    ELSE
      IF args->>'revision' IS DISTINCT FROM d.revision::text THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
      UPDATE nku_notice_text_v1.drafts SET plan=args->'plan',payload_hash=args->>'payload_hash',revision=revision+1
        WHERE draft_id=d.draft_id RETURNING * INTO d;
    END IF;
    data:=jsonb_build_object('draft_id',d.draft_id,'kind','task','workspace_ref',w.workspace_ref,'revision',d.revision,
      'payload_hash',d.payload_hash,'status',d.status,'expires_epoch',d.expires_at);
  ELSIF op='confirm' THEN
    IF args->>'revision' IS DISTINCT FROM d.revision::text OR args->>'payload_hash' IS DISTINCT FROM d.payload_hash THEN
      RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    INSERT INTO nku_notice_text_v1.confirmations VALUES(args->>'confirmation_hash',d.draft_id,d.revision,d.payload_hash,
      least(now_s+600,s.expires_at),NULL);
    data:=jsonb_build_object('confirmation_id',args->>'confirmation_id','draft_id',d.draft_id,'revision',d.revision,
      'payload_hash',d.payload_hash,'expires_epoch',least(now_s+600,s.expires_at));
  ELSIF op='commit' THEN
    IF c.used_at IS NOT NULL THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
    IF EXISTS(SELECT 1 FROM nku_notice_text_v1.tasks WHERE workspace_ref=w.workspace_ref
      AND notice_id=d.plan->'notice'->>'notice_id') THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
    INSERT INTO nku_notice_text_v1.tasks VALUES(args->>'resource_id',w.workspace_ref,d.draft_id,d.plan->'notice'->>'notice_id',now_s);
    UPDATE nku_notice_text_v1.confirmations SET used_at=now_s WHERE confirmation_hash=c.confirmation_hash;
    UPDATE nku_notice_text_v1.drafts SET status='committed' WHERE draft_id=d.draft_id;
    data:=jsonb_build_object('task_id',args->>'resource_id','revision',d.revision);
  END IF;
  INSERT INTO nku_notice_text_v1.idempotency VALUES(s.owner_subject_id,v_operation,args->>'key',args->>'request_hash',data);
  RETURN jsonb_build_object('ok',true,'data',data);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_notice_text_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_notice_text_v1_rpc(text,jsonb) TO service_role;
COMMIT;
