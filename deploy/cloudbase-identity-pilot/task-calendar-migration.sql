-- Run AFTER identity, competition OAuth and notice-text migrations.
-- Only new calendar tables; shared owner lock and original notice rows retained.
BEGIN;
CREATE SCHEMA nku_task_calendar_v1;
REVOKE ALL ON SCHEMA nku_task_calendar_v1 FROM PUBLIC,anon,authenticated;
CREATE TABLE nku_task_calendar_v1.states (
  workspace_ref text NOT NULL REFERENCES nku_identity_pilot_v1.workspaces(workspace_ref),
  task_id text NOT NULL, revision integer NOT NULL CHECK(revision>0),
  status text NOT NULL CHECK(status IN ('pending','completed','cancelled')),
  scheduled_start timestamptz, scheduled_end timestamptz,
  reminder_minutes integer CHECK(reminder_minutes IN (0,5,15,30,60)),
  PRIMARY KEY(workspace_ref,task_id),
  CHECK((scheduled_start IS NULL AND scheduled_end IS NULL) OR
        (scheduled_start IS NOT NULL AND scheduled_end IS NOT NULL AND scheduled_start<scheduled_end)),
  CHECK(reminder_minutes IS NULL OR scheduled_start IS NOT NULL)
);
CREATE TABLE nku_task_calendar_v1.idempotency (
  owner_subject_id text NOT NULL, workspace_ref text NOT NULL,
  key text NOT NULL, task_id text NOT NULL, request_hash text NOT NULL,
  response jsonb NOT NULL, PRIMARY KEY(owner_subject_id,key)
);
ALTER TABLE nku_task_calendar_v1.states ENABLE ROW LEVEL SECURITY;
ALTER TABLE nku_task_calendar_v1.idempotency ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA nku_task_calendar_v1 FROM PUBLIC,anon,authenticated;

CREATE FUNCTION nku_task_calendar_v1.now_epoch() RETURNS bigint
LANGUAGE sql VOLATILE SET search_path='' AS $$ SELECT floor(extract(epoch FROM clock_timestamp()))::bigint $$;
REVOKE ALL ON FUNCTION nku_task_calendar_v1.now_epoch() FROM PUBLIC,anon,authenticated;

CREATE FUNCTION nku_task_calendar_v1.rows(workspace text) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 WITH source AS (
   SELECT t.task_id,1 revision,t.confirmed_at, f.payload notice,'{}'::jsonb plan
     FROM nku_identity_pilot_v1.tasks t JOIN nku_identity_pilot_v1.drafts d ON d.draft_id=t.draft_id
     JOIN nku_identity_pilot_v1.fixtures f ON f.payload_hash=d.payload_hash WHERE d.workspace_ref=workspace
   UNION ALL
   SELECT t.task_id,d.revision,t.confirmed_at,d.plan->'notice',d.plan
     FROM nku_notice_text_v1.tasks t JOIN nku_notice_text_v1.drafts d ON d.draft_id=t.draft_id
     WHERE t.workspace_ref=workspace
 ), defaults AS (
   SELECT *, CASE WHEN notice->'event'->>'precision'='datetime' THEN notice->'event'->>'start'
                 ELSE plan->'selected_slot'->>'start' END initial_start,
             CASE WHEN notice->'event'->>'precision'='datetime' THEN notice->'event'->>'end'
                 ELSE plan->'selected_slot'->>'end' END initial_end FROM source
 ) SELECT coalesce(jsonb_agg(jsonb_build_object('task_id',s.task_id,'workspace_ref',workspace,
   'revision',s.revision,'confirmed_epoch',s.confirmed_at,'notice',s.notice,
   'plan_kind',s.plan->>'kind',
   'planning_constraints',jsonb_build_object('available_windows',coalesce(s.plan->'available_windows','[]'::jsonb),
     'buffers',coalesce(s.plan->'buffers','{"before_minutes":0,"after_minutes":0}'::jsonb)),
   'calendar_state',CASE WHEN c.task_id IS NULL THEN jsonb_build_object('calendar_revision',0,'status','pending',
     'scheduled_start',s.initial_start,'scheduled_end',s.initial_end,'reminder_minutes',NULL)
     ELSE jsonb_build_object('calendar_revision',c.revision,'status',c.status,
       'scheduled_start',c.scheduled_start,'scheduled_end',c.scheduled_end,'reminder_minutes',c.reminder_minutes) END)
   ORDER BY s.task_id),'[]'::jsonb) FROM defaults s LEFT JOIN nku_task_calendar_v1.states c
     ON c.workspace_ref=workspace AND c.task_id=s.task_id;
$$;
REVOKE ALL ON FUNCTION nku_task_calendar_v1.rows(text) FROM PUBLIC,anon,authenticated;

-- Existing notice/time calculations and notice commits see the same calendar
-- state. This prevents status changes from leaving stale busy intervals behind.
CREATE OR REPLACE FUNCTION nku_notice_text_v1.snapshot(session_hash text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE base jsonb; full_rows jsonb; compact jsonb; workspace text;
BEGIN
 base:=public.nku_identity_pilot_v1_rpc('get_workspace',jsonb_build_object('session_hash',session_hash));
 IF base->>'ok' IS DISTINCT FROM 'true' THEN RETURN base; END IF;
 workspace:=base->'data'->>'workspace_ref';
 base:=public.nku_identity_pilot_v1_rpc('records',jsonb_build_object('session_hash',session_hash));
 IF base->>'ok' IS DISTINCT FROM 'true' THEN RETURN base; END IF;
 full_rows:=nku_task_calendar_v1.rows(workspace);
 SELECT coalesce(jsonb_agg(jsonb_build_object('task_id',t->>'task_id','workspace_ref',workspace,
   'revision',t->'revision','confirmed_epoch',t->'confirmed_epoch','calendar_state',t->'calendar_state',
   'notice',CASE WHEN t->>'plan_kind' IS NULL THEN t->'notice'
    ELSE jsonb_build_object('plan_version','notice-text-pilot-v1','kind',t->>'plan_kind',
      'notice',t->'notice'||jsonb_build_object('source_spans','[]'::jsonb,'materials','[]'::jsonb),
      'selected_slot',CASE WHEN t->>'plan_kind'='deadline_feasibility' AND
        t->'calendar_state'->>'scheduled_start' IS NOT NULL THEN jsonb_build_object(
          'start',t->'calendar_state'->>'scheduled_start','end',t->'calendar_state'->>'scheduled_end',
          'duration_minutes',t->'notice'->'estimated_minutes') ELSE 'null'::jsonb END) END)),'[]'::jsonb)
   INTO compact FROM jsonb_array_elements(full_rows) t;
 RETURN jsonb_build_object('ok',true,'data',base->'data'||jsonb_build_object('tasks',compact,
   'workspace_ref',workspace,'dataset_mode','fictional_notice_text',
   'records_revision',md5(jsonb_build_object('schedule',base->'data'->'schedule','tasks',compact)::text)));
END;
$$;
REVOKE ALL ON FUNCTION nku_notice_text_v1.snapshot(text) FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.nku_task_calendar_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE auth jsonb; result jsonb; data jsonb; workspace text; owner text; task jsonb;
 state jsonb; old_state jsonb; idem nku_task_calendar_v1.idempotency%ROWTYPE;
 expected text[]; auth_keys text[]; now_s bigint:=nku_task_calendar_v1.now_epoch();
 start_at timestamptz; end_at timestamptz;
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
   IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN
   RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','task-calendar-v1'));
 END IF;
 auth_keys:=CASE args->>'principal_kind' WHEN 'browser' THEN ARRAY['principal_kind','session_hash','csrf_hash']
   WHEN 'agent' THEN ARRAY['principal_kind','grant_mode','grant_hash','audience'] ELSE NULL END;
 expected:=CASE op WHEN 'records' THEN ARRAY[]::text[] WHEN 'lookup' THEN ARRAY['task_id','key','request_hash']
   WHEN 'update' THEN ARRAY['task_id','key','request_hash','records_revision','state'] ELSE NULL END;
 IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR octet_length(args::text)>32768 OR auth_keys IS NULL
   OR expected IS NULL OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(auth_keys||expected)
   OR NOT args ?& (auth_keys||expected) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF args->>'principal_kind'='agent' AND op<>'records' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 SELECT jsonb_object_agg(k,args->k) INTO auth FROM unnest(auth_keys) k;
 -- The existing notice RPC validates grants/session/approval/expiry and takes
 -- the ORIGINAL owner lock; the lock remains held through this transaction.
 result:=public.nku_notice_text_v1_rpc('records',auth);
 IF result->>'ok' IS DISTINCT FROM 'true' THEN RETURN result; END IF;
 workspace:=result->'data'->>'workspace_ref';
 IF op='records' THEN RETURN jsonb_build_object('ok',true,'data',result->'data'||
     jsonb_build_object('tasks',nku_task_calendar_v1.rows(workspace))); END IF;
 SELECT owner_subject_id INTO owner FROM nku_identity_pilot_v1.browser_sessions
   WHERE token_hash=args->>'session_hash' AND csrf_hash=args->>'csrf_hash';
 IF owner IS NULL THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 SELECT value INTO task FROM jsonb_array_elements(nku_task_calendar_v1.rows(workspace))
   WHERE value->>'task_id'=args->>'task_id';
 IF task IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 IF coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$' OR
   coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$' THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 SELECT * INTO idem FROM nku_task_calendar_v1.idempotency WHERE owner_subject_id=owner AND key=args->>'key';
 IF FOUND THEN
   IF idem.workspace_ref<>workspace OR idem.task_id<>args->>'task_id' THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
   IF idem.request_hash<>args->>'request_hash' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   RETURN jsonb_build_object('ok',true,'data',idem.response);
 END IF;
 IF op='lookup' THEN RETURN jsonb_build_object('ok',true,'data','null'::jsonb); END IF;
 IF result->'data'->>'records_revision' IS DISTINCT FROM args->>'records_revision' THEN
   RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 state:=args->'state'; old_state:=task->'calendar_state';
 IF jsonb_typeof(state) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(state))<>6
   OR NOT state ?& ARRAY['workspace_ref','expected_revision','status','scheduled_start','scheduled_end','reminder_minutes']
   OR state->>'workspace_ref' IS DISTINCT FROM workspace OR coalesce(state->>'status','') NOT IN ('pending','completed','cancelled')
   OR jsonb_typeof(state->'status') IS DISTINCT FROM 'string'
   OR NOT (state->'scheduled_start'='null'::jsonb OR (jsonb_typeof(state->'scheduled_start')='string' AND
      state->>'scheduled_start' ~ 'T.*(Z|[+-][0-9]{2}:[0-9]{2})$'))
   OR NOT (state->'scheduled_end'='null'::jsonb OR (jsonb_typeof(state->'scheduled_end')='string' AND
      state->>'scheduled_end' ~ 'T.*(Z|[+-][0-9]{2}:[0-9]{2})$'))
   OR coalesce(state->>'expected_revision','') !~ '^[0-9]{1,10}$'
   OR jsonb_typeof(state->'expected_revision')<>'number'
   OR (state->>'expected_revision')::bigint>2147483646
   OR NOT (state->'reminder_minutes'='null'::jsonb OR state->'reminder_minutes' IN ('0'::jsonb,'5'::jsonb,'15'::jsonb,'30'::jsonb,'60'::jsonb))
   THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF state->>'expected_revision' IS DISTINCT FROM old_state->>'calendar_revision' THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 BEGIN
   start_at:=(state->>'scheduled_start')::timestamptz; end_at:=(state->>'scheduled_end')::timestamptz;
 EXCEPTION WHEN OTHERS THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END;
 IF (start_at IS NULL)<>(end_at IS NULL) OR start_at>=end_at OR
   (state->'reminder_minutes'<>'null'::jsonb AND start_at IS NULL) THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF task->'notice'->'event'->>'precision'<>'unknown' AND
   (start_at IS DISTINCT FROM (old_state->>'scheduled_start')::timestamptz OR end_at IS DISTINCT FROM (old_state->>'scheduled_end')::timestamptz) THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF state->>'status'<>'pending' AND
   (start_at IS DISTINCT FROM (old_state->>'scheduled_start')::timestamptz OR end_at IS DISTINCT FROM (old_state->>'scheduled_end')::timestamptz) THEN
   RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 IF state->>'status'='pending' AND start_at IS NOT NULL AND (old_state->>'status'<>'pending' OR
   start_at IS DISTINCT FROM (old_state->>'scheduled_start')::timestamptz OR end_at IS DISTINCT FROM (old_state->>'scheduled_end')::timestamptz) THEN
   IF start_at<to_timestamp(now_s) THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
   IF task->'notice'->'event'->>'precision'='unknown' AND
     (task->'notice'->'due'->>'precision'<>'datetime' OR end_at>(task->'notice'->'due'->>'at')::timestamptz OR
      start_at<(task->'notice'->>'earliest_start')::timestamptz OR
      extract(epoch FROM end_at-start_at) IS DISTINCT FROM (task->'notice'->>'estimated_minutes')::numeric*60) THEN
     RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 END IF;
 INSERT INTO nku_task_calendar_v1.states VALUES(workspace,args->>'task_id',
   (state->>'expected_revision')::integer+1,state->>'status',start_at,end_at,(state->>'reminder_minutes')::integer)
   ON CONFLICT(workspace_ref,task_id) DO UPDATE SET revision=EXCLUDED.revision,status=EXCLUDED.status,
     scheduled_start=EXCLUDED.scheduled_start,scheduled_end=EXCLUDED.scheduled_end,reminder_minutes=EXCLUDED.reminder_minutes;
 SELECT value INTO task FROM jsonb_array_elements(nku_task_calendar_v1.rows(workspace))
   WHERE value->>'task_id'=args->>'task_id';
 data:=(task - 'calendar_state' - 'planning_constraints' - 'plan_kind' - 'workspace_ref')||(task->'calendar_state');
 INSERT INTO nku_task_calendar_v1.idempotency VALUES(owner,workspace,args->>'key',args->>'task_id',args->>'request_hash',data);
 RETURN jsonb_build_object('ok',true,'data',data);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_task_calendar_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_task_calendar_v1_rpc(text,jsonb) TO service_role;
COMMIT;
