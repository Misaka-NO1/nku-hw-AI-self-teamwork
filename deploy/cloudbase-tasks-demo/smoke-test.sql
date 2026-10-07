-- Database assertions only; NOT browser/Agent or real service-key verification.
-- Every temporary session/draft/task is rolled back, existing data is untouched.
BEGIN;
DO $$
DECLARE
  a jsonb := jsonb_build_object('session_hash',repeat('a',64),'csrf_hash',repeat('b',64));
  b jsonb := jsonb_build_object('session_hash',repeat('1',64),'csrf_hash',repeat('2',64));
  h text;
  r jsonb;
  saved jsonb;
BEGIN
  PERFORM set_config('request.jwt.claims','{"role":"anon"}',true);
  r := public.nku_tasks_demo_v1_rpc('probe','{}');
  ASSERT r->>'code'='FORBIDDEN', 'anonymous RPC must be denied';
  PERFORM set_config('request.jwt.claims','{"role":"authenticated"}',true);
  r := public.nku_tasks_demo_v1_rpc('probe','{}');
  ASSERT r->>'code'='FORBIDDEN', 'ordinary user RPC must be denied';
  PERFORM set_config('request.jwt.claims','{"role":"service_role"}',true);
  ASSERT public.nku_tasks_demo_v1_rpc('probe','{}')->>'ok'='true', 'server probe must pass';
  r := public.nku_tasks_demo_v1_rpc('create_session',jsonb_build_object(
    'token_hash',repeat('a',64),'csrf_hash',repeat('b',64),'subject_id','db_smoke_owner_a','workspace_ref','db_smoke_workspace_a'));
  ASSERT r->>'ok'='true', 'session create failed';
  r := public.nku_tasks_demo_v1_rpc('create_session',jsonb_build_object(
    'token_hash',repeat('1',64),'csrf_hash',repeat('2',64),'subject_id','db_smoke_owner_b','workspace_ref','db_smoke_workspace_b'));
  ASSERT r->>'ok'='true', 'second session create failed';
  SELECT payload_hash INTO h FROM nku_tasks_demo_v1.fixtures WHERE payload->'event'->>'precision'='datetime' LIMIT 1;
  r := public.nku_tasks_demo_v1_rpc('create_draft',a || jsonb_build_object('workspace_ref','db_smoke_workspace_a',
    'draft_id','db_smoke_draft_a','payload_hash',h,'key','db-smoke-create','request_hash',repeat('c',64)));
  ASSERT r->>'ok'='true', 'draft create failed';
  r := public.nku_tasks_demo_v1_rpc('list_tasks',a || '{"workspace_ref":"db_smoke_workspace_a"}'::jsonb);
  ASSERT r->'data'='[]'::jsonb, 'draft must not be a saved task';
  r := public.nku_tasks_demo_v1_rpc('confirm',a || jsonb_build_object('draft_id','db_smoke_draft_a',
    'revision',2,'payload_hash',h,'confirmation_id','db_smoke_confirmation','confirmation_hash',repeat('e',64),
    'key','db-smoke-confirm-bad','request_hash',repeat('d',64)));
  ASSERT r->>'code'='STALE_REVISION', 'changed revision must be denied';
  r := public.nku_tasks_demo_v1_rpc('confirm',a || jsonb_build_object('draft_id','db_smoke_draft_a',
    'revision',1,'payload_hash',h,'confirmation_id','db_smoke_confirmation','confirmation_hash',repeat('e',64),
    'key','db-smoke-confirm','request_hash',repeat('d',64)));
  ASSERT r->>'ok'='true', 'confirmation failed';
  saved := public.nku_tasks_demo_v1_rpc('commit',a || jsonb_build_object('confirmation_hash',repeat('e',64),
    'task_id','db_smoke_task_a','key','db-smoke-commit','request_hash',repeat('f',64)));
  ASSERT saved->>'ok'='true' AND saved->'data'->>'task_id'='db_smoke_task_a', 'commit failed';
  r := public.nku_tasks_demo_v1_rpc('commit',a || jsonb_build_object('confirmation_hash',repeat('e',64),
    'task_id','must_not_create_duplicate','key','db-smoke-commit','request_hash',repeat('f',64)));
  ASSERT r=saved, 'retry must return the same task';
  r := public.nku_tasks_demo_v1_rpc('list_tasks',a || '{"workspace_ref":"db_smoke_workspace_a"}'::jsonb);
  ASSERT jsonb_array_length(r->'data')=1, 'exactly one committed task required';
  r := public.nku_tasks_demo_v1_rpc('get_task',b || '{"task_id":"db_smoke_task_a"}'::jsonb);
  ASSERT r->>'code'='NOT_FOUND', 'cross-owner read must be denied';
  r := public.nku_tasks_demo_v1_rpc('commit',(a - 'csrf_hash') || jsonb_build_object(
    'confirmation_hash',repeat('e',64),'task_id','no_csrf','key','db-smoke-commit','request_hash',repeat('f',64)));
  ASSERT r->>'code'='FORBIDDEN', 'CSRF-less idempotent retry must be denied';
  SELECT payload_hash INTO h FROM nku_tasks_demo_v1.fixtures WHERE jsonb_array_length(payload->'needs_confirmation')>0 LIMIT 1;
  r := public.nku_tasks_demo_v1_rpc('create_draft',a || jsonb_build_object('workspace_ref','db_smoke_workspace_a',
    'draft_id','db_smoke_ambiguous','payload_hash',h,'key','db-smoke-ambiguous','request_hash',repeat('9',64)));
  ASSERT r->>'ok'='true', 'ambiguous draft should be previewable';
  r := public.nku_tasks_demo_v1_rpc('confirm',a || jsonb_build_object('draft_id','db_smoke_ambiguous',
    'revision',1,'payload_hash',h,'confirmation_id','not_issued','confirmation_hash',repeat('8',64),
    'key','db-smoke-confirm-ambiguous','request_hash',repeat('7',64)));
  ASSERT r->>'code'='CONFIRMATION_REQUIRED', 'ambiguous draft must not be confirmed';
  UPDATE nku_tasks_demo_v1.workspaces SET expires_at=0 WHERE workspace_ref='db_smoke_workspace_a';
  r := public.nku_tasks_demo_v1_rpc('get_task',a || '{"task_id":"db_smoke_task_a"}'::jsonb);
  ASSERT r->>'code'='NOT_FOUND', 'expired workspace must be denied';
END;
$$;
SELECT 'PASS: database transaction, retry, owner, expiry, CSRF and ambiguity assertions' AS db_smoke_result;
ROLLBACK;
