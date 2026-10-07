-- Additive opt-in. Existing sessions/grants are NEVER extended by migration.
-- Fresh verified login and fresh owner consent are required. No data deletion.
BEGIN;
DO $$ BEGIN
  IF to_regprocedure('public.nku_identity_pilot_v1_ephemeral_rpc(text,jsonb)') IS NULL THEN
    ALTER FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb) RENAME TO nku_identity_pilot_v1_ephemeral_rpc;
  END IF;
  IF to_regprocedure('public.nku_competition_oauth_v1_ephemeral_rpc(text,jsonb)') IS NULL THEN
    ALTER FUNCTION public.nku_competition_oauth_v1_rpc(text,jsonb) RENAME TO nku_competition_oauth_v1_ephemeral_rpc;
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.nku_identity_pilot_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; owner text; ws text; claims jsonb;
BEGIN
  claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
  IF claims->>'role' IS DISTINCT FROM 'service_role' THEN RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN'); END IF;
  IF op='persistent_probe' AND args='{}'::jsonb THEN
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('schema_version','persistent-auth-v1'));
  END IF;
  IF op='login' AND args ? 'persistent' THEN
    IF jsonb_typeof(args) IS DISTINCT FROM 'object' OR args->'persistent' IS DISTINCT FROM 'true'::jsonb
      OR (SELECT count(*) FROM jsonb_object_keys(args))<>6
      OR NOT args ?& ARRAY['subject_id','token_hash','csrf_hash','workspace_ref','previous_session_hash','persistent']
      OR coalesce(args->>'token_hash','') !~ '^[0-9a-f]{64}$'
      OR coalesce(args->>'csrf_hash','') !~ '^[0-9a-f]{64}$'
      OR coalesce(args->>'previous_session_hash','') !~ '^[0-9a-f]{64}$'
      OR coalesce(args->>'workspace_ref','') !~ '^pilot_workspace_[A-Za-z0-9_-]{24}$' THEN
      RETURN nku_identity_pilot_v1.err(422,'VALIDATION_ERROR');
    END IF;
    owner:=args->>'subject_id';
    IF NOT EXISTS(SELECT 1 FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=owner) THEN
      RETURN nku_identity_pilot_v1.err(403,'FORBIDDEN');
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(owner,604022002));
    -- Retain this verified owner's already imported fictional timetable.
    UPDATE nku_identity_pilot_v1.workspaces w SET expires_at=253370736000
      FROM nku_identity_pilot_v1.owner_workspaces ow
      WHERE ow.subject_id=owner AND w.workspace_ref=ow.workspace_ref AND w.owner_subject_id=owner;
    result:=public.nku_identity_pilot_v1_ephemeral_rpc(op,args-'persistent');
    IF result->'ok' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'persistent login rejected'; END IF;
    ws:=result->'data'->>'workspace_ref';
    UPDATE nku_identity_pilot_v1.workspaces SET expires_at=253370736000 WHERE workspace_ref=ws AND owner_subject_id=owner;
    UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=253370736000
      WHERE token_hash=args->>'token_hash' AND owner_subject_id=owner AND workspace_ref=ws;
    RETURN jsonb_build_object('ok',true,'data',jsonb_build_object('workspace_ref',ws,'expires_epoch',253370736000::bigint));
  END IF;
  RETURN public.nku_identity_pilot_v1_ephemeral_rpc(op,args);
END $$;

CREATE OR REPLACE FUNCTION public.nku_competition_oauth_v1_rpc(op text,args jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb;
BEGIN
  -- Delegate all existing role, scope, callback, owner, expiry and replay gates.
  result:=public.nku_competition_oauth_v1_ephemeral_rpc(op,args);
  IF op='authorize_start' AND result->'ok'='true'::jsonb THEN
    UPDATE nku_competition_oauth_v1.requests q SET grant_expires_at=253370736000
      FROM nku_identity_pilot_v1.browser_sessions s
      WHERE q.transaction_hash=args->>'transaction_hash' AND q.source_session_hash=s.token_hash
        AND s.token_hash=args->>'session_hash' AND s.expires_at=253370736000;
    -- The one-use authorization request/code still expires in 120 seconds.
  END IF;
  RETURN result;
END $$;

REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_ephemeral_rpc(text,jsonb), public.nku_competition_oauth_v1_ephemeral_rpc(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb), public.nku_competition_oauth_v1_rpc(text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.nku_identity_pilot_v1_rpc(text,jsonb), public.nku_competition_oauth_v1_rpc(text,jsonb) TO service_role;
COMMIT;
