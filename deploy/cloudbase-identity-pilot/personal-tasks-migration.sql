-- Existing environment, existing two-user identity policy and calendar schema.
-- No anonymous access; old demo:read grants acquire NO personal permissions.
BEGIN;
CREATE TABLE nku_task_calendar_v1.entry_drafts (
 owner_subject_id text NOT NULL, draft_id text NOT NULL,
 content jsonb NOT NULL, payload_hash text NOT NULL,
 expires_at bigint NOT NULL, task_id text,
 PRIMARY KEY(owner_subject_id,draft_id)
);
CREATE TABLE nku_task_calendar_v1.entries (
 owner_subject_id text NOT NULL, task_id text NOT NULL,
 content jsonb NOT NULL, revision integer NOT NULL DEFAULT 1,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','cancelled')),
 confirmed_epoch bigint NOT NULL,
 PRIMARY KEY(owner_subject_id,task_id)
);
CREATE TABLE nku_task_calendar_v1.entry_idempotency (
 owner_subject_id text NOT NULL, operation text NOT NULL, key text NOT NULL,
 request_hash text NOT NULL, response jsonb NOT NULL,
 PRIMARY KEY(owner_subject_id,operation,key)
);
ALTER TABLE nku_task_calendar_v1.entry_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_task_calendar_v1.entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_task_calendar_v1.entry_idempotency ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_task_calendar_v1.entry_drafts,nku_task_calendar_v1.entries,
 nku_task_calendar_v1.entry_idempotency FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.nku_personal_tasks_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 g nku_competition_oauth_v1.grants%ROWTYPE;
 d nku_task_calendar_v1.entry_drafts%ROWTYPE;
 t nku_task_calendar_v1.entries%ROWTYPE;
 idem nku_task_calendar_v1.entry_idempotency%ROWTYPE;
 result jsonb; data jsonb; auth_keys text[]; expected text[]; owner text;
 now_s bigint:=floor(extract(epoch FROM clock_timestamp()));
 read_ok boolean:=false; write_ok boolean:=false; state jsonb; c jsonb;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','personal-tasks-v1')); END IF;
 auth_keys:=CASE args->>'principal_kind'
  WHEN 'browser' THEN ARRAY['principal_kind','session_hash','csrf_hash']
  WHEN 'agent' THEN ARRAY['principal_kind','grant_mode','grant_hash','audience'] ELSE NULL END;
 expected:=CASE op WHEN 'access' THEN ARRAY[]::text[] WHEN 'records' THEN ARRAY[]::text[]
  WHEN 'draft' THEN ARRAY['content','payload_hash','draft_id','key','request_hash']
  WHEN 'commit' THEN ARRAY['draft_id','payload_hash','task_id','key','request_hash']
  WHEN 'update' THEN ARRAY['task_id','state','key','request_hash'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>32768
  OR auth_keys IS NULL OR expected IS NULL
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(auth_keys||expected)
  OR NOT args ?& (auth_keys||expected) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF args->>'principal_kind'='browser' THEN
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
  read_ok:=true; write_ok:=s.csrf_hash=args->>'csrf_hash';
 ELSE
  IF args->>'grant_mode'<>'competition' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
   AND audience=args->>'audience' AND expires_at>now_s;
  SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=g.source_session_hash;
  read_ok:='tasks:read'=ANY(g.scopes); write_ok:='tasks:write'=ANY(g.scopes);
 END IF;
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 owner:=s.owner_subject_id;
 PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022002));
 -- Original gate rechecks session, approved_subjects, owner/workspace and expiry.
 result:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',s.token_hash));
 IF result->>'ok' IS DISTINCT FROM 'true' THEN RETURN result; END IF;
 IF args->>'principal_kind'='agent' THEN
  SELECT * INTO g FROM nku_competition_oauth_v1.grants WHERE token_hash=args->>'grant_hash'
   AND audience=args->>'audience' AND expires_at>floor(extract(epoch FROM clock_timestamp())) FOR UPDATE;
  IF g.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 END IF;
 IF op='access' THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('can_read',coalesce(read_ok,false),'can_write',coalesce(write_ok,false))); END IF;
 IF NOT coalesce(read_ok,false) OR (op<>'records' AND NOT coalesce(write_ok,false)) THEN
  RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='records' THEN
  SELECT coalesce(jsonb_agg(jsonb_build_object('task_id',task_id,'content',content,
   'revision',revision,'status',status,'confirmed_epoch',confirmed_epoch) ORDER BY confirmed_epoch,task_id),'[]'::jsonb)
   INTO data FROM nku_task_calendar_v1.entries WHERE owner_subject_id=owner;
  RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('items',data));
 END IF;
 IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$'
  OR coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$'
  OR (op IN ('draft','commit') AND coalesce(args->>'payload_hash','') !~ '^[0-9a-f]{64}$') THEN
  RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 SELECT * INTO idem FROM nku_task_calendar_v1.entry_idempotency
  WHERE owner_subject_id=owner AND operation=op AND key=args->>'key';
 IF FOUND THEN
  IF idem.request_hash IS DISTINCT FROM args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF op='draft' AND NOT EXISTS(SELECT 1 FROM nku_task_calendar_v1.entry_drafts
   WHERE owner_subject_id=owner AND draft_id=idem.response->>'draft_id' AND expires_at>now_s) THEN
   RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  RETURN jsonb_build_object('ok',true,'data',idem.response);
 END IF;
 IF op='draft' THEN
  c:=args->'content';
  IF jsonb_typeof(c) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(c))<>8
   OR NOT c ?& ARRAY['title','kind','due_at','due_date','reminder_at','notes','scheduled_slots','reminder_minutes']
   THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
  END IF;
  IF jsonb_typeof(c->'title') IS DISTINCT FROM 'string' OR length(btrim(c->>'title')) NOT BETWEEN 1 AND 200
   OR c->>'kind' NOT IN ('reminder','deadline','event') OR jsonb_typeof(c->'notes') IS DISTINCT FROM 'string'
   OR length(c->>'notes')>2000 OR jsonb_typeof(c->'scheduled_slots') IS DISTINCT FROM 'array'
   OR jsonb_array_length(c->'scheduled_slots')>8
   OR NOT (c->'reminder_minutes'='null'::jsonb OR c->'reminder_minutes' IN ('0'::jsonb,'5'::jsonb,'15'::jsonb,'30'::jsonb,'60'::jsonb)) THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  DELETE FROM nku_task_calendar_v1.entry_drafts WHERE owner_subject_id=owner AND expires_at<=now_s;
  IF (SELECT count(*) FROM nku_task_calendar_v1.entry_drafts WHERE owner_subject_id=owner)>=200
   OR (SELECT count(*) FROM nku_task_calendar_v1.entries WHERE owner_subject_id=owner)>=500 THEN
   RETURN nku_identity_pilot_v1.err(429,'RATE_LIMITED'); END IF;
  INSERT INTO nku_task_calendar_v1.entry_drafts VALUES(owner,args->>'draft_id',c,args->>'payload_hash',now_s+86400,NULL);
  data:=jsonb_build_object('draft_id',args->>'draft_id','payload_hash',args->>'payload_hash','content',c);
 ELSIF op='commit' THEN
  SELECT * INTO d FROM nku_task_calendar_v1.entry_drafts WHERE owner_subject_id=owner AND draft_id=args->>'draft_id' FOR UPDATE;
  IF d.draft_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  IF d.expires_at<=now_s THEN RETURN nku_identity_pilot_v1.err(410,'TOKEN_EXPIRED'); END IF;
  IF d.payload_hash IS DISTINCT FROM args->>'payload_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF d.task_id IS NULL THEN
   INSERT INTO nku_task_calendar_v1.entries VALUES(owner,args->>'task_id',d.content,1,'pending',now_s);
   UPDATE nku_task_calendar_v1.entry_drafts SET task_id=args->>'task_id' WHERE owner_subject_id=owner AND draft_id=d.draft_id;
   d.task_id:=args->>'task_id';
  END IF;
  data:=jsonb_build_object('task_id',d.task_id);
 ELSE
  SELECT * INTO t FROM nku_task_calendar_v1.entries WHERE owner_subject_id=owner AND task_id=args->>'task_id' FOR UPDATE;
  IF t.task_id IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  state:=args->'state';
  IF jsonb_typeof(state) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(state))<>3
   OR NOT state ?& ARRAY['expected_revision','status','reminder_minutes']
   OR jsonb_typeof(state->'expected_revision') IS DISTINCT FROM 'number'
   OR coalesce(state->>'expected_revision','') !~ '^[0-9]{1,9}$'
   OR coalesce(state->>'status','') NOT IN ('pending','completed','cancelled')
   OR NOT (state->'reminder_minutes'='null'::jsonb OR state->'reminder_minutes' IN ('0'::jsonb,'5'::jsonb,'15'::jsonb,'30'::jsonb,'60'::jsonb)) THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  IF (state->>'expected_revision')::integer<>t.revision THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  IF state->'reminder_minutes'<>'null'::jsonb AND t.content->'reminder_at'='null'::jsonb
   AND jsonb_array_length(t.content->'scheduled_slots')=0 THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
  UPDATE nku_task_calendar_v1.entries SET revision=revision+1,status=state->>'status',
   content=jsonb_set(content,'{reminder_minutes}',state->'reminder_minutes')
   WHERE owner_subject_id=owner AND task_id=t.task_id RETURNING * INTO t;
  data:=jsonb_build_object('task_id',t.task_id,'content',t.content,'revision',t.revision,'status',t.status,'confirmed_epoch',t.confirmed_epoch);
 END IF;
 INSERT INTO nku_task_calendar_v1.entry_idempotency VALUES(owner,op,args->>'key',args->>'request_hash',data);
 RETURN jsonb_build_object('ok',true,'data',data);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_personal_tasks_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_personal_tasks_v1_rpc(text,jsonb) TO service_role;
COMMIT;
