-- Delete only an explicitly confirmed, current owner's single saved task.
-- Original draft/audit records stay; active tasks disappear from every reader.
-- No new login/grant scopes, no anonymous rights, no bulk deletion.
BEGIN;
CREATE TABLE nku_task_calendar_v1.delete_receipts (
 owner_subject_id text NOT NULL, key text NOT NULL, task_id text NOT NULL,
 request_hash text NOT NULL, response jsonb NOT NULL,
 PRIMARY KEY(owner_subject_id,key)
);
ALTER TABLE nku_task_calendar_v1.delete_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nku_task_calendar_v1.delete_receipts FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.nku_task_delete_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE s nku_identity_pilot_v1.browser_sessions%ROWTYPE;
 receipt nku_task_calendar_v1.delete_receipts%ROWTYPE;
 result jsonb; task jsonb; workspace text; owner text; revision integer; personal boolean;
 expected text[]:=ARRAY['principal_kind','session_hash','csrf_hash','workspace_ref','task_id',
  'expected_revision','confirmed','key','request_hash'];
BEGIN
 IF coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'role'
  IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 IF op='probe' AND args='{}'::jsonb THEN RETURN jsonb_build_object('ok',true,'data',
  jsonb_build_object('schema_version','task-delete-v1')); END IF;
 IF op IS DISTINCT FROM 'delete' OR jsonb_typeof(args) IS DISTINCT FROM 'object'
  OR octet_length(args::text)>32768 OR NOT args ?& expected
  OR (SELECT count(*) FROM jsonb_object_keys(args))<>cardinality(expected)
  OR args->>'principal_kind' IS DISTINCT FROM 'browser'
  OR args->'confirmed' IS DISTINCT FROM 'true'::jsonb
  OR jsonb_typeof(args->'expected_revision') IS DISTINCT FROM 'number'
  OR coalesce(args->>'expected_revision','') !~ '^[0-9]{1,10}$'
  OR (args->>'expected_revision')::bigint>2147483646
  OR coalesce(args->>'key','') !~ '^[A-Za-z0-9._:-]{8,128}$'
  OR coalesce(args->>'request_hash','') !~ '^[0-9a-f]{64}$'
  OR jsonb_typeof(args->'task_id') IS DISTINCT FROM 'string'
  OR length(args->>'task_id') NOT BETWEEN 1 AND 128
  THEN RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR'); END IF;
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 owner:=s.owner_subject_id;
 PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022002));
 -- Re-read under the same owner lock used by commits/status updates/revocation.
 SELECT * INTO s FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=args->>'session_hash';
 IF s.token_hash IS NULL THEN RETURN nku_identity_pilot_v1.err(401,'AUTH_REQUIRED'); END IF;
 IF s.csrf_hash IS DISTINCT FROM args->>'csrf_hash' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
 result:=public.nku_task_calendar_v1_rpc('records',jsonb_build_object(
  'principal_kind','browser','session_hash',s.token_hash,'csrf_hash',s.csrf_hash));
 IF result->>'ok' IS DISTINCT FROM 'true' THEN RETURN result; END IF;
 workspace:=result->'data'->>'workspace_ref';
 IF args->>'workspace_ref' IS DISTINCT FROM workspace THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
 SELECT * INTO receipt FROM nku_task_calendar_v1.delete_receipts WHERE owner_subject_id=owner AND key=args->>'key';
 IF FOUND THEN
  IF receipt.task_id IS DISTINCT FROM args->>'task_id' OR receipt.request_hash IS DISTINCT FROM args->>'request_hash'
   THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
  RETURN jsonb_build_object('ok',true,'data',receipt.response);
 END IF;
 SELECT e.revision INTO revision FROM nku_task_calendar_v1.entries e
  WHERE e.owner_subject_id=owner AND e.task_id=args->>'task_id' FOR UPDATE;
 personal:=FOUND;
 IF NOT personal THEN
  SELECT value INTO task FROM jsonb_array_elements(result->'data'->'tasks')
   WHERE value->>'task_id'=args->>'task_id';
  IF task IS NULL THEN RETURN nku_identity_pilot_v1.err(404,'NOT_FOUND'); END IF;
  revision:=(task->'calendar_state'->>'calendar_revision')::integer;
 END IF;
 IF revision IS DISTINCT FROM (args->>'expected_revision')::integer
  THEN RETURN nku_identity_pilot_v1.err(409,'STALE_REVISION'); END IF;
 IF personal THEN
  DELETE FROM nku_task_calendar_v1.entries WHERE owner_subject_id=owner AND task_id=args->>'task_id';
 ELSE
  DELETE FROM nku_notice_text_v1.tasks WHERE workspace_ref=workspace AND task_id=args->>'task_id';
  DELETE FROM nku_identity_pilot_v1.tasks t USING nku_identity_pilot_v1.drafts d
   WHERE t.draft_id=d.draft_id AND d.workspace_ref=workspace AND t.task_id=args->>'task_id';
 END IF;
 DELETE FROM nku_task_calendar_v1.states WHERE workspace_ref=workspace AND task_id=args->>'task_id';
 result:=jsonb_build_object('task_id',args->>'task_id','deleted',true);
 INSERT INTO nku_task_calendar_v1.delete_receipts VALUES(owner,args->>'key',args->>'task_id',args->>'request_hash',result);
 RETURN jsonb_build_object('ok',true,'data',result);
END;
$$;
REVOKE ALL ON FUNCTION public.nku_task_delete_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_task_delete_v1_rpc(text,jsonb) TO service_role;
COMMIT;
