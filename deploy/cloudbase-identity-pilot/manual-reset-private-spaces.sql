-- DESTRUCTIVE MANUAL MAINTENANCE, NOT A MIGRATION OR STARTUP SCRIPT.
-- Run ONLY after the owner confirms ALL campus-tool users must start over.
-- No normal UI recovery. Does not delete cloud resources, credentials, code,
-- registered-account allowlists, fixtures, rate limits or other projects.
-- Schema drift / outside references / lock contention abort the transaction.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $reset$
DECLARE
  cleared text[] := ARRAY[
    'nku_identity_pilot_v1.workspaces',
    'nku_identity_pilot_v1.owner_workspaces',
    'nku_identity_pilot_v1.browser_sessions',
    'nku_identity_pilot_v1.drafts',
    'nku_identity_pilot_v1.confirmations',
    'nku_identity_pilot_v1.tasks',
    'nku_identity_pilot_v1.schedules',
    'nku_identity_pilot_v1.idempotency',
    'nku_identity_pilot_v1.import_tickets',
    'nku_identity_pilot_v1.oauth_requests',
    'nku_identity_pilot_v1.oauth_codes',
    'nku_identity_pilot_v1.oauth_grants',
    'nku_identity_pilot_v1.personal_schedule_drafts',
    'nku_identity_pilot_v1.personal_schedule_confirmations',
    'nku_identity_pilot_v1.personal_schedules',
    'nku_identity_pilot_v1.device_enrollments',
    'nku_identity_pilot_v1.agent_devices',
    'nku_identity_pilot_v1.browser_visitors',
    'nku_identity_pilot_v1.native_identity_accounts',
    'nku_identity_pilot_v1.native_browser_intakes',
    'nku_competition_oauth_v1.requests',
    'nku_competition_oauth_v1.codes',
    'nku_competition_oauth_v1.grants',
    'nku_notice_text_v1.drafts',
    'nku_notice_text_v1.confirmations',
    'nku_notice_text_v1.tasks',
    'nku_notice_text_v1.idempotency',
    'nku_task_calendar_v1.states',
    'nku_task_calendar_v1.idempotency',
    'nku_task_calendar_v1.entry_drafts',
    'nku_task_calendar_v1.entries',
    'nku_task_calendar_v1.entry_idempotency',
    'nku_task_calendar_v1.delete_receipts',
    'nku_degree_progress_v1.reports',
    'nku_degree_progress_v1.idempotency',
    'nku_degree_progress_v1.agent_drafts'
  ];
  kept text[] := ARRAY[
    'nku_identity_pilot_v1.approved_subjects',
    'nku_identity_pilot_v1.fixtures',
    'nku_identity_pilot_v1.rate_limits'
  ];
  expected text[];
  actual text[];
  table_name text;
  remaining bigint;
  fixtures_before bigint;
  roster_before bigint;
BEGIN
  -- Historical campus-tool module installed by an earlier deployment. Its four
  -- private tables reference the same workspaces; do not confuse it with an
  -- unrelated project or use CASCADE. Only this exact optional inventory is allowed.
  IF to_regnamespace('nku_personal_degree_v1') IS NOT NULL THEN
    cleared := cleared || ARRAY[
      'nku_personal_degree_v1.degree_drafts',
      'nku_personal_degree_v1.degree_confirmations',
      'nku_personal_degree_v1.degree_snapshots',
      'nku_personal_degree_v1.degree_idempotency'
    ];
  END IF;
  expected := cleared || kept;
  SELECT array_agg(n.nspname || '.' || c.relname ORDER BY n.nspname,c.relname)
    INTO actual FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname IN ('nku_identity_pilot_v1','nku_competition_oauth_v1',
      'nku_notice_text_v1','nku_task_calendar_v1','nku_degree_progress_v1','nku_personal_degree_v1')
      AND c.relkind IN ('r','p','f');
  SELECT array_agg(v ORDER BY v) INTO expected FROM unnest(expected) v;
  IF actual IS DISTINCT FROM expected THEN
    RAISE EXCEPTION 'Reset aborted: project table inventory changed';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=ANY(
      ARRAY(SELECT v::regclass::oid FROM unnest(expected) v)) AND NOT c.relrowsecurity) THEN
    RAISE EXCEPTION 'Reset aborted: project RLS state changed';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE contype='f'
      AND confrelid=ANY(ARRAY(SELECT v::regclass::oid FROM unnest(cleared) v))
      AND NOT conrelid=ANY(ARRAY(SELECT v::regclass::oid FROM unnest(cleared) v))) THEN
    RAISE EXCEPTION 'Reset aborted: a preserved or outside table references private data';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_trigger WHERE NOT tgisinternal AND (tgtype & 32) <> 0
      AND tgrelid=ANY(ARRAY(SELECT v::regclass::oid FROM unnest(cleared) v))) THEN
    RAISE EXCEPTION 'Reset aborted: an unreviewed truncate trigger exists';
  END IF;
  -- Lock the fixed inventory; never enumerate outside schemas for mutation.
  EXECUTE 'LOCK TABLE ' || array_to_string(expected, ', ') || ' IN ACCESS EXCLUSIVE MODE';
  SELECT count(*) INTO fixtures_before FROM nku_identity_pilot_v1.fixtures;
  SELECT count(*) INTO roster_before FROM nku_identity_pilot_v1.approved_subjects
    WHERE subject_id !~ '^visitor_[0-9a-f]{64}$';
  -- These are generated private-space owners, NOT registered login accounts.
  -- Leaving them behind would prevent the same verified identity starting over.
  DELETE FROM nku_identity_pilot_v1.approved_subjects
    WHERE subject_id ~ '^visitor_[0-9a-f]{64}$';
  EXECUTE 'TRUNCATE TABLE ' || array_to_string(cleared, ', ') || ' RESTRICT';
  FOREACH table_name IN ARRAY cleared LOOP
    EXECUTE 'SELECT count(*) FROM ' || table_name INTO remaining;
    IF remaining <> 0 THEN RAISE EXCEPTION 'Reset verification failed'; END IF;
  END LOOP;
  IF fixtures_before <> (SELECT count(*) FROM nku_identity_pilot_v1.fixtures)
      OR roster_before <> (SELECT count(*) FROM nku_identity_pilot_v1.approved_subjects
        WHERE subject_id !~ '^visitor_[0-9a-f]{64}$') THEN
    RAISE EXCEPTION 'Reset verification failed: preserved data changed';
  END IF;
END;
$reset$;
COMMIT;
SELECT 'private_spaces_reset' AS result,
  (SELECT count(*) FROM nku_identity_pilot_v1.workspaces) AS spaces,
  (SELECT count(*) FROM nku_identity_pilot_v1.owner_workspaces) AS owners,
  (SELECT count(*) FROM nku_identity_pilot_v1.personal_schedules) AS timetables,
  (SELECT count(*) FROM nku_task_calendar_v1.entries) AS calendar_entries,
  (SELECT count(*) FROM nku_degree_progress_v1.reports) AS degree_reports,
  (SELECT count(*) FROM nku_identity_pilot_v1.native_identity_accounts) AS identity_links,
  (SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions) AS sessions,
  (SELECT count(*) FROM nku_competition_oauth_v1.grants) AS oauth_grants;
