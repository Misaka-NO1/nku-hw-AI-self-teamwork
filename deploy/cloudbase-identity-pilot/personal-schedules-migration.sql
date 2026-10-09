-- Additive personal timetable storage. Existing fixture/task/calendar data stays intact.
-- Only the existing server RPC role can execute; owner is always session-derived.
BEGIN;
CREATE TABLE IF NOT EXISTS nku_identity_pilot_v1.personal_schedule_drafts (
 draft_id text PRIMARY KEY, workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces,
 payload jsonb NOT NULL, payload_hash text NOT NULL, revision integer NOT NULL DEFAULT 1,
 base_revision integer NOT NULL, status text NOT NULL DEFAULT 'draft', expires_at bigint NOT NULL
);
CREATE TABLE IF NOT EXISTS nku_identity_pilot_v1.personal_schedules (
 workspace_ref text PRIMARY KEY REFERENCES nku_identity_pilot_v1.workspaces,
 schedule_id text NOT NULL, payload jsonb NOT NULL, revision integer NOT NULL, confirmed_at bigint NOT NULL
);
ALTER TABLE nku_identity_pilot_v1.personal_schedule_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_identity_pilot_v1.personal_schedules ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.personal_schedule_drafts,nku_identity_pilot_v1.personal_schedules FROM PUBLIC,anon,authenticated,service_role;
DO $$ BEGIN
 IF to_regprocedure('public.nku_identity_pilot_v1_before_personal_schedules_rpc(text,jsonb)') IS NULL THEN
  ALTER FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) RENAME TO nku_identity_pilot_v1_before_personal_schedules_rpc;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION public.nku_identity_pilot_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
 s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 d nku_identity_pilot_v1.personal_schedule_drafts%ROWTYPE;
 p nku_identity_pilot_v1.personal_schedules%ROWTYPE;
 receipt_draft_id text;
 idem nku_identity_pilot_v1.idempotency%ROWTYPE;
 result jsonb; data jsonb; baseline jsonb; current_rev integer:=0;
 now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
 personal_op boolean:=false;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role' IS DISTINCT FROM 'service_role'
 THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>1048576
 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF op='personal_schedule_probe' AND args='{}'::jsonb THEN
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','personal-schedules-v1'));
 END IF;
 -- Existing authorization and compatibility RPCs resolve read principals themselves.
 IF op IN ('records','current_schedule') THEN
  baseline:=public.nku_identity_pilot_v1_before_personal_schedules_rpc('records',args);
  IF baseline->>'ok' IS DISTINCT FROM 'true' THEN RETURN baseline; END IF;
  SELECT ps.* INTO p FROM nku_identity_pilot_v1.personal_schedules ps
   WHERE ps.workspace_ref=coalesce(baseline->'data'->'schedule'->>'workspace_ref',args->>'workspace_ref');
  -- records without a current fixture schedule still needs the verified session workspace.
  IF p.workspace_ref IS NULL AND coalesce(args->>'principal_kind','browser')='browser' THEN
   SELECT ps.* INTO p FROM nku_identity_pilot_v1.personal_schedules ps
    JOIN nku_identity_pilot_v1.browser_sessions bs ON bs.workspace_ref=ps.workspace_ref
    WHERE bs.token_hash=args->>'session_hash' AND bs.expires_at>now_s;
  END IF;
  IF p.workspace_ref IS NULL AND args->>'principal_kind'='agent' THEN
   -- The previous RPC has already verified audience, scope, approval and grant.
   SELECT ps.* INTO p FROM nku_identity_pilot_v1.personal_schedules ps
    JOIN nku_identity_pilot_v1.browser_sessions bs ON bs.workspace_ref=ps.workspace_ref
    JOIN nku_identity_pilot_v1.oauth_grants og ON og.source_session_hash=bs.token_hash
    WHERE og.token_hash=args->>'grant_hash' AND og.expires_at>now_s AND bs.expires_at>now_s;
  END IF;
  IF p.workspace_ref IS NOT NULL THEN
   data:=jsonb_build_object('schedule_id',p.schedule_id,'workspace_ref',p.workspace_ref,
    'revision',p.revision,'timetable',p.payload,'confirmed_epoch',p.confirmed_at);
   baseline:=jsonb_set(baseline,'{data,schedule}',data);
   baseline:=jsonb_set(baseline,'{data,personal_uploads}','true'::jsonb);
   baseline:=jsonb_set(baseline,'{data,dataset_kind}',p.payload->'dataset_kind');
  END IF;
  IF op='records' THEN RETURN baseline; END IF;
  IF baseline->'data'->'schedule'='null'::jsonb THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  RETURN jsonb_build_object('ok',true,'data',baseline->'data'->'schedule');
 END IF;
 IF op='create_draft' AND args->>'kind'='schedule' AND args ? 'payload' THEN personal_op:=true;
 ELSIF op IN ('get_draft','confirm') THEN
  SELECT * INTO d FROM nku_identity_pilot_v1.personal_schedule_drafts WHERE draft_id=args->>'draft_id';
  personal_op:=d.draft_id IS NOT NULL;
 ELSIF op='commit' THEN
  SELECT draft_id INTO receipt_draft_id FROM nku_identity_pilot_v1.personal_schedule_confirmations WHERE confirmation_hash=args->>'confirmation_hash';
  SELECT * INTO d FROM nku_identity_pilot_v1.personal_schedule_drafts WHERE draft_id=receipt_draft_id;
  personal_op:=d.draft_id IS NOT NULL;
 END IF;
 IF NOT personal_op THEN RETURN public.nku_identity_pilot_v1_before_personal_schedules_rpc(op,args); END IF;
 -- Deliberately browser-only: no new OAuth scope, extension token, or model write authority.
 IF coalesce(args->>'principal_kind','browser')<>'browser' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(s.owner_subject_id,604022002));
 result:=public.nku_identity_pilot_v1_before_personal_schedules_rpc('get_workspace',
  jsonb_build_object('session_hash',s.token_hash,'workspace_ref',s.workspace_ref));
 IF result->>'ok' IS DISTINCT FROM 'true' THEN RETURN result; END IF;
 IF args ? 'workspace_ref' AND args->>'workspace_ref' IS DISTINCT FROM s.workspace_ref
 THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 IF op<>'get_draft' AND s.csrf_hash IS DISTINCT FROM args->>'csrf_hash'
 THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op<>'create_draft' THEN
  SELECT * INTO d FROM nku_identity_pilot_v1.personal_schedule_drafts
   WHERE draft_id=d.draft_id AND workspace_ref=s.workspace_ref FOR UPDATE;
  IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 END IF;
 IF op='get_draft' THEN
  IF d.expires_at<=now_s AND d.status<>'committed' THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('draft_id',d.draft_id,'kind','schedule',
   'workspace_ref',d.workspace_ref,'payload',d.payload,'payload_hash',d.payload_hash,'revision',d.revision,
   'status',d.status,'expires_epoch',d.expires_at));
 END IF;
 IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$' OR coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$'
 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 SELECT * INTO idem FROM nku_identity_pilot_v1.idempotency WHERE owner_subject_id=s.owner_subject_id
  AND operation='personal_schedule:'||op AND key=args->>'key';
 IF FOUND THEN
  IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  RETURN jsonb_build_object('ok',true,'data',idem.response);
 END IF;
 SELECT * INTO p FROM nku_identity_pilot_v1.personal_schedules WHERE workspace_ref=s.workspace_ref;
 IF p.workspace_ref IS NOT NULL THEN current_rev:=p.revision;
 ELSE SELECT coalesce(max(revision),0) INTO current_rev FROM nku_identity_pilot_v1.schedules WHERE workspace_ref=s.workspace_ref; END IF;
 IF op='create_draft' THEN
  IF jsonb_typeof(args->'payload') IS DISTINCT FROM 'object' OR args->'payload'->>'schema_version'<>'1.0.0'
   OR coalesce(args->'payload'->>'dataset_kind','') NOT IN ('personal','demo')
   OR jsonb_typeof(args->'payload'->'courses') IS DISTINCT FROM 'array'
   OR jsonb_array_length(args->'payload'->'courses') NOT BETWEEN 1 AND 300
   OR coalesce(args->>'payload_hash','') !~ '^[0-9a-f]{64}$'
   OR coalesce(args->>'draft_id','') !~ '^draft_[A-Za-z0-9_-]{24}$'
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  IF (SELECT count(*) FROM nku_identity_pilot_v1.personal_schedule_drafts
   WHERE workspace_ref=s.workspace_ref AND status='draft' AND expires_at>now_s)>=100
  THEN RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
  INSERT INTO nku_identity_pilot_v1.personal_schedule_drafts(draft_id,workspace_ref,payload,payload_hash,base_revision,expires_at)
   VALUES(args->>'draft_id',s.workspace_ref,args->'payload',args->>'payload_hash',current_rev,now_s+86400);
  data:=jsonb_build_object('draft_id',args->>'draft_id','kind','schedule','workspace_ref',s.workspace_ref,
   'revision',1,'payload_hash',args->>'payload_hash','status','draft','expires_epoch',now_s+86400);
 ELSE
  IF d.expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  IF d.status<>'draft' OR current_rev<>d.base_revision THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF op='confirm' THEN
   IF args->>'revision' IS DISTINCT FROM d.revision::text OR args->>'payload_hash' IS DISTINCT FROM d.payload_hash
    OR coalesce(args->>'confirmation_hash','') !~ '^[0-9a-f]{64}$'
   THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   -- The old confirmation FK references fixture drafts; personal receipts live separately.
   INSERT INTO nku_identity_pilot_v1.personal_schedule_confirmations
    VALUES(args->>'confirmation_hash',d.draft_id,d.payload_hash,least(now_s+600,s.expires_at),NULL);
   data:=jsonb_build_object('confirmation_id',args->>'confirmation_id','draft_id',d.draft_id,
    'revision',d.revision,'payload_hash',d.payload_hash,'expires_epoch',least(now_s+600,s.expires_at));
  ELSE
   IF args->>'kind'<>'schedule' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.personal_schedule_confirmations pc
    WHERE pc.confirmation_hash=args->>'confirmation_hash' AND pc.draft_id=d.draft_id
     AND pc.payload_hash=d.payload_hash AND pc.expires_at>now_s AND pc.used_at IS NULL)
   THEN RETURN nku_identity_pilot_v1.err(409,'CONFIRMATION_REQUIRED'); END IF;
   INSERT INTO nku_identity_pilot_v1.personal_schedules VALUES(s.workspace_ref,coalesce(p.schedule_id,args->>'resource_id'),d.payload,current_rev+1,now_s)
    ON CONFLICT(workspace_ref) DO UPDATE SET payload=excluded.payload,revision=excluded.revision,confirmed_at=excluded.confirmed_at
    RETURNING * INTO p;
   UPDATE nku_identity_pilot_v1.personal_schedule_drafts SET status='committed' WHERE draft_id=d.draft_id;
   UPDATE nku_identity_pilot_v1.personal_schedule_confirmations SET used_at=now_s WHERE confirmation_hash=args->>'confirmation_hash';
   data:=jsonb_build_object('schedule_id',p.schedule_id,'revision',p.revision);
  END IF;
 END IF;
 INSERT INTO nku_identity_pilot_v1.idempotency VALUES(s.owner_subject_id,'personal_schedule:'||op,args->>'key',args->>'request_hash',data);
 RETURN jsonb_build_object('ok',true,'data',data);
END $$;
CREATE TABLE IF NOT EXISTS nku_identity_pilot_v1.personal_schedule_confirmations (
 confirmation_hash text PRIMARY KEY, draft_id text NOT NULL REFERENCES nku_identity_pilot_v1.personal_schedule_drafts,
 payload_hash text NOT NULL, expires_at bigint NOT NULL, used_at bigint
);
ALTER TABLE nku_identity_pilot_v1.personal_schedule_confirmations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_identity_pilot_v1.personal_schedule_confirmations FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_before_personal_schedules_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) TO service_role;
COMMIT;
