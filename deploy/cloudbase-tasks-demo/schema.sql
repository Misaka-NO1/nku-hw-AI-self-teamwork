-- Isolated, fictional TasksPage storage. Never alters existing business tables.
-- Run once using the CloudBase SQL editor. No passwords or API keys belong here.
BEGIN;
CREATE SCHEMA nku_tasks_demo_v1;
REVOKE ALL ON SCHEMA nku_tasks_demo_v1 FROM PUBLIC, anon, authenticated;
CREATE TABLE nku_tasks_demo_v1.sessions (
  token_hash text PRIMARY KEY, subject_id text UNIQUE NOT NULL,
  csrf_hash text NOT NULL, expires_at bigint NOT NULL
);
CREATE TABLE nku_tasks_demo_v1.workspaces (
  workspace_ref text PRIMARY KEY, subject_id text UNIQUE NOT NULL
    REFERENCES nku_tasks_demo_v1.sessions(subject_id) ON DELETE CASCADE,
  expires_at bigint NOT NULL
);
CREATE TABLE nku_tasks_demo_v1.fixtures (
  payload_hash text PRIMARY KEY, payload jsonb NOT NULL
);
CREATE TABLE nku_tasks_demo_v1.drafts (
  draft_id text PRIMARY KEY, workspace_ref text NOT NULL
    REFERENCES nku_tasks_demo_v1.workspaces ON DELETE CASCADE,
  payload_hash text NOT NULL REFERENCES nku_tasks_demo_v1.fixtures,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','committed')),
  expires_at bigint NOT NULL
);
CREATE TABLE nku_tasks_demo_v1.confirmations (
  confirmation_hash text PRIMARY KEY, draft_id text NOT NULL
    REFERENCES nku_tasks_demo_v1.drafts ON DELETE CASCADE,
  expires_at bigint NOT NULL, used_at bigint
);
CREATE TABLE nku_tasks_demo_v1.tasks (
  task_id text PRIMARY KEY, draft_id text UNIQUE NOT NULL
    REFERENCES nku_tasks_demo_v1.drafts ON DELETE CASCADE,
  confirmed_at bigint NOT NULL
);
CREATE TABLE nku_tasks_demo_v1.idempotency (
  subject_id text NOT NULL REFERENCES nku_tasks_demo_v1.sessions(subject_id) ON DELETE CASCADE,
  operation text NOT NULL, key text NOT NULL, request_hash text NOT NULL,
  response jsonb NOT NULL, PRIMARY KEY (subject_id, operation, key)
);
-- No direct client grants. RLS is defence in depth, not the RPC auth boundary.
ALTER TABLE nku_tasks_demo_v1.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_tasks_demo_v1.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_tasks_demo_v1.fixtures ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_tasks_demo_v1.drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_tasks_demo_v1.confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_tasks_demo_v1.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_tasks_demo_v1.idempotency ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_tasks_demo_v1 FROM PUBLIC, anon, authenticated;

CREATE FUNCTION public.nku_tasks_demo_v1_rpc(op text, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  claims jsonb;
  now_s bigint := floor(extract(epoch FROM clock_timestamp()));
  s nku_tasks_demo_v1.sessions%ROWTYPE;
  w nku_tasks_demo_v1.workspaces%ROWTYPE;
  d nku_tasks_demo_v1.drafts%ROWTYPE;
  c nku_tasks_demo_v1.confirmations%ROWTYPE;
  idem nku_tasks_demo_v1.idempotency%ROWTYPE;
  result jsonb;
  notice jsonb;
BEGIN
  -- CloudBase may expose RPC even without GRANT EXECUTE: explicit guard required.
  claims := coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb;
  IF claims->>'role' IS DISTINCT FROM 'service_role' THEN
    RETURN jsonb_build_object('ok',false,'status',403,'code','FORBIDDEN','message','Server role required');
  END IF;
  IF op = 'probe' THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','tasks-demo-v1'));
  END IF;
  IF op = 'create_session' THEN
    -- Bound public-demo growth; cleanup is confined to this test schema.
    PERFORM pg_advisory_xact_lock(604021001);
    DELETE FROM nku_tasks_demo_v1.sessions WHERE expires_at <= now_s;
    IF (SELECT count(*) FROM nku_tasks_demo_v1.sessions) >= 100 THEN
      RETURN jsonb_build_object('ok',false,'status',429,'code','RATE_LIMITED','message','Demo workspace limit reached');
    END IF;
    INSERT INTO nku_tasks_demo_v1.sessions VALUES
      (args->>'token_hash', args->>'subject_id', args->>'csrf_hash', now_s + 86400);
    INSERT INTO nku_tasks_demo_v1.workspaces VALUES
      (args->>'workspace_ref', args->>'subject_id', now_s + 86400);
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object(
      'workspace_ref',args->>'workspace_ref','expires_epoch',now_s+86400));
  END IF;
  SELECT * INTO s FROM nku_tasks_demo_v1.sessions
    WHERE token_hash = args->>'session_hash' AND expires_at > now_s;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok',false,'status',401,'code','AUTH_REQUIRED','message','Browser session required');
  END IF;
  -- Serialize confirmation/commit/idempotency per owner, including cross-instance calls.
  PERFORM pg_advisory_xact_lock(hashtextextended(s.subject_id, 604021002));
  SELECT * INTO w FROM nku_tasks_demo_v1.workspaces
    WHERE subject_id = s.subject_id AND expires_at > now_s;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok',false,'status',404,'code','NOT_FOUND','message','Workspace not found');
  END IF;
  IF op NOT IN ('list_tasks','get_task','get_draft','create_draft','confirm','commit') THEN
    RETURN jsonb_build_object('ok',false,'status',422,'code','VALIDATION_ERROR','message','Unsupported operation');
  END IF;
  IF op IN ('create_draft','confirm','commit') THEN
    IF s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN
      RETURN jsonb_build_object('ok',false,'status',403,'code','FORBIDDEN','message','CSRF validation failed');
    END IF;
    IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$' THEN
      RETURN jsonb_build_object('ok',false,'status',422,'code','VALIDATION_ERROR','message','Invalid idempotency key');
    END IF;
  END IF;
  IF op IN ('list_tasks','create_draft') AND w.workspace_ref IS DISTINCT FROM args->>'workspace_ref' THEN
    RETURN jsonb_build_object('ok',false,'status',404,'code','NOT_FOUND','message','Workspace not found');
  END IF;
  IF op = 'list_tasks' OR op = 'get_task' THEN
    SELECT coalesce(jsonb_agg(jsonb_build_object('task_id',t.task_id,
      'workspace_ref',w.workspace_ref,'revision',1,'notice',f.payload,
      'confirmed_epoch',t.confirmed_at) ORDER BY t.confirmed_at DESC,t.task_id), '[]'::jsonb)
    INTO result FROM nku_tasks_demo_v1.tasks t
      JOIN nku_tasks_demo_v1.drafts ds ON ds.draft_id=t.draft_id
      JOIN nku_tasks_demo_v1.fixtures f ON f.payload_hash=ds.payload_hash
      WHERE ds.workspace_ref=w.workspace_ref
        AND (op='list_tasks' OR t.task_id=args->>'task_id');
    IF op='get_task' THEN
      IF jsonb_array_length(result)=0 THEN
        RETURN jsonb_build_object('ok',false,'status',404,'code','NOT_FOUND','message','Task not found');
      END IF;
      result := result->0;
    END IF;
    RETURN jsonb_build_object('ok',true,'data',result);
  END IF;
  IF op IN ('get_draft','confirm','commit') THEN
    IF op='commit' THEN
      SELECT * INTO c FROM nku_tasks_demo_v1.confirmations WHERE confirmation_hash=args->>'confirmation_hash';
      SELECT * INTO d FROM nku_tasks_demo_v1.drafts WHERE draft_id=c.draft_id AND workspace_ref=w.workspace_ref;
    ELSE
      SELECT * INTO d FROM nku_tasks_demo_v1.drafts WHERE draft_id=args->>'draft_id' AND workspace_ref=w.workspace_ref;
    END IF;
    IF d.draft_id IS NULL THEN
      RETURN jsonb_build_object('ok',false,'status',404,'code','NOT_FOUND','message','Draft not found');
    END IF;
    IF d.expires_at<=now_s THEN
      RETURN jsonb_build_object('ok',false,'status',410,'code','TOKEN_EXPIRED','message','Draft expired');
    END IF;
    SELECT payload INTO notice FROM nku_tasks_demo_v1.fixtures WHERE payload_hash=d.payload_hash;
    IF op='get_draft' THEN
      RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('draft_id',d.draft_id,
        'kind','task','workspace_ref',d.workspace_ref,'revision',1,'payload',notice,
        'payload_hash',d.payload_hash,'status',d.status,'expires_epoch',d.expires_at));
    END IF;
  END IF;
  SELECT * INTO idem FROM nku_tasks_demo_v1.idempotency
    WHERE subject_id=s.subject_id AND operation=op AND key=args->>'key';
  IF FOUND THEN
    IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN
      RETURN jsonb_build_object('ok',false,'status',409,'code','STALE_REVISION','message','Idempotency key reused with different input');
    END IF;
    RETURN jsonb_build_object('ok',true,'data',idem.response);
  END IF;
  IF op='create_draft' THEN
    SELECT payload INTO notice FROM nku_tasks_demo_v1.fixtures WHERE payload_hash=args->>'payload_hash';
    IF NOT FOUND THEN
      RETURN jsonb_build_object('ok',false,'status',403,'code','DEMO_ONLY','message','Checked fictional fixture required');
    END IF;
    IF (SELECT count(*) FROM nku_tasks_demo_v1.drafts WHERE workspace_ref=w.workspace_ref)>=10 THEN
      RETURN jsonb_build_object('ok',false,'status',429,'code','RATE_LIMITED','message','Demo draft limit reached');
    END IF;
    INSERT INTO nku_tasks_demo_v1.drafts(draft_id,workspace_ref,payload_hash,expires_at)
      VALUES(args->>'draft_id',w.workspace_ref,args->>'payload_hash',w.expires_at);
    result := jsonb_build_object('draft_id',args->>'draft_id','kind','task',
      'workspace_ref',w.workspace_ref,'revision',1,'payload_hash',args->>'payload_hash',
      'status','draft','expires_epoch',w.expires_at);
  ELSE
    IF coalesce(jsonb_array_length(notice->'needs_confirmation'),1)>0 THEN
      RETURN jsonb_build_object('ok',false,'status',409,'code','CONFIRMATION_REQUIRED','message','Notice fields still need confirmation');
    END IF;
    IF d.status<>'draft' THEN
      RETURN jsonb_build_object('ok',false,'status',409,'code','STALE_REVISION','message','Draft already committed');
    END IF;
    IF op='confirm' THEN
      IF args->>'revision' IS DISTINCT FROM '1' OR d.payload_hash IS DISTINCT FROM args->>'payload_hash' THEN
        RETURN jsonb_build_object('ok',false,'status',409,'code','STALE_REVISION','message','Draft revision changed');
      END IF;
      INSERT INTO nku_tasks_demo_v1.confirmations VALUES(args->>'confirmation_hash',d.draft_id,now_s+600,NULL);
      result := jsonb_build_object('confirmation_id',args->>'confirmation_id','draft_id',d.draft_id,
        'revision',1,'payload_hash',d.payload_hash,'expires_epoch',now_s+600);
    ELSE
      IF c.expires_at<=now_s THEN
        RETURN jsonb_build_object('ok',false,'status',410,'code','TOKEN_EXPIRED','message','Confirmation expired');
      END IF;
      IF c.used_at IS NOT NULL THEN
        RETURN jsonb_build_object('ok',false,'status',409,'code','CONFIRMATION_REQUIRED','message','Confirmation already used');
      END IF;
      INSERT INTO nku_tasks_demo_v1.tasks VALUES(args->>'task_id',d.draft_id,now_s);
      UPDATE nku_tasks_demo_v1.confirmations SET used_at=now_s WHERE confirmation_hash=c.confirmation_hash;
      UPDATE nku_tasks_demo_v1.drafts SET status='committed' WHERE draft_id=d.draft_id;
      result := jsonb_build_object('task_id',args->>'task_id','revision',1);
    END IF;
  END IF;
  INSERT INTO nku_tasks_demo_v1.idempotency VALUES(s.subject_id,op,args->>'key',args->>'request_hash',result);
  RETURN jsonb_build_object('ok',true,'data',result);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_tasks_demo_v1_rpc(text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.nku_tasks_demo_v1_rpc(text,jsonb) TO service_role;
COMMIT;
