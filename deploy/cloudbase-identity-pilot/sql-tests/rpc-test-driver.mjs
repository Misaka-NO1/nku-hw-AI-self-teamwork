// Private pipe for Python API integration tests. PostgreSQL stays in this
// process while HTTP application instances restart. Never used in deployment.
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createInterface } from 'node:readline';
const pg=new PGlite();
await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
await pg.exec(await readFile(new URL('../schema.sql',import.meta.url),'utf8'));
// Additive compatibility is exercised only in this private test pipe.
await pg.exec(await readFile(new URL('../competition-oauth-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../notice-text-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../task-calendar-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../task-oauth-scopes-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../personal-tasks-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../persistent-auth-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../personal-schedules-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../device-login-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../agent-device-binding-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../task-delete-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../browser-visitor-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../visitor-identity-first-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../native-identity-registry-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../native-browser-binding-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../degree-progress-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../degree-agent-import-migration.sql',import.meta.url),'utf8'));
await pg.exec(await readFile(new URL('../degree-in-progress-migration.sql',import.meta.url),'utf8'));
await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
const canonical=value=>value && typeof value==='object' ? Array.isArray(value) ? value.map(canonical) :
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])) : value;
for(const name of ['timetable.demo.json','notice-event.demo.json','notice-deadline.demo.json','notice-ambiguous.demo.json']) {
  const raw=JSON.parse(await readFile(new URL('../../../fixtures/'+name,import.meta.url),'utf8'));
  const hash=createHash('sha256').update(JSON.stringify(canonical(raw))).digest('hex');
  await pg.query('INSERT INTO nku_identity_pilot_v1.fixtures VALUES($1,$2,$3::jsonb)',[hash,name.startsWith('timetable')?'schedule':'task',JSON.stringify(raw)]);
}
process.stdout.write('{"ready":true}\n');
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  try {
    const {op,args}=JSON.parse(line);
    if(op==='__test_reset_guard__') {
      const table = args.kind==='outside_fk' ? 'public.reset_guard_fixture' :
        args.kind==='schema_drift' ? 'nku_degree_progress_v1.reset_guard_fixture' : null;
      if(!table)throw new Error('invalid fixed test case');
      await pg.exec(`CREATE TABLE ${table}(ref text REFERENCES nku_identity_pilot_v1.workspaces(workspace_ref));`);
      let rejected=false;
      try {
        await pg.exec(await readFile(new URL('../manual-reset-private-spaces.sql',import.meta.url),'utf8'));
      } catch { rejected=true; await pg.exec('ROLLBACK;'); }
      await pg.exec(`DROP TABLE ${table};`);
      const result=await pg.query('SELECT count(*) spaces FROM nku_identity_pilot_v1.workspaces');
      process.stdout.write(JSON.stringify({ok:true,data:{rejected,spaces:result.rows[0].spaces}})+'\n');continue;
    }
    if(op==='__test_reset_private_spaces__') {
      // Fixed manual-maintenance script in isolated test DB only. This driver
      // and the reset script are excluded from deployment packages.
      await pg.exec(await readFile(new URL('../manual-reset-private-spaces.sql',import.meta.url),'utf8'));
      const result=await pg.query(`SELECT
        (SELECT count(*) FROM nku_identity_pilot_v1.workspaces) spaces,
        (SELECT count(*) FROM nku_identity_pilot_v1.fixtures) fixtures,
        (SELECT count(*) FROM nku_identity_pilot_v1.approved_subjects) approved,
        (SELECT count(*) FROM nku_degree_progress_v1.reports) reports,
        has_function_privilege('anon','public.nku_degree_agent_v1_rpc(text,jsonb)','EXECUTE') anonymous_execute,
        has_function_privilege('service_role','public.nku_degree_agent_v1_rpc(text,jsonb)','EXECUTE') backend_execute`);
      process.stdout.write(JSON.stringify({ok:true,data:result.rows[0]})+'\n');continue;
    }
    if(op==='__test_expire_degree_draft__') {
      if(!/^degree_[0-9a-f]{32}$/.test(args.draft_id ?? ''))throw new Error('invalid draft');
      await pg.query('UPDATE nku_degree_progress_v1.agent_drafts SET expires_epoch=0 WHERE draft_id=$1',[args.draft_id]);
      process.stdout.write('{"ok":true,"data":{}}\n');continue;
    }
    if(op.startsWith('__degree_agent__:')) {
      const result=await pg.query('SELECT public.nku_degree_agent_v1_rpc($1,$2::jsonb) result',
        [op.slice('__degree_agent__:'.length),JSON.stringify(args)]);
      process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');continue;
    }
    if(op.startsWith('__degree__:')) {
      const result=await pg.query('SELECT public.nku_degree_progress_v1_rpc($1,$2::jsonb) result',
        [op.slice('__degree__:'.length),JSON.stringify(args)]);
      process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');continue;
    }
    if(op.startsWith('__native__:')) {
      const result=await pg.query('SELECT public.nku_native_browser_v1_rpc($1,$2::jsonb) result',
        [op.slice('__native__:'.length),JSON.stringify(args)]);
      process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');continue;
    }
    if(op==='__test_legacy_visitor_fixture__') {
      // Historical identities seeded ONLY in this isolated superuser test pipe.
      // The renamed legacy RPC is inaccessible to deployed service_role callers.
      const result=await pg.query("SELECT public.nku_identity_pilot_v1_before_identity_first_rpc('visitor_begin',$1::jsonb) result",[JSON.stringify(args)]);
      process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');continue;
    }
    if(op==='__test_identity_counts__') {
      const result=await pg.query('SELECT (SELECT count(*) FROM nku_identity_pilot_v1.browser_visitors) visitors,(SELECT count(*) FROM nku_identity_pilot_v1.owner_workspaces) owners,(SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions) sessions');
      process.stdout.write(JSON.stringify({ok:true,data:result.rows[0]})+'\n');continue;
    }
    if(op.startsWith('__task_delete__:')) {
      const result=await pg.query('SELECT public.nku_task_delete_v1_rpc($1,$2::jsonb) result',
        [op.slice('__task_delete__:'.length),JSON.stringify(args)]);
      process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');continue;
    }
    if (op==='__test_calendar_clock__') {
      if (!Number.isSafeInteger(args.epoch) || args.epoch<1700000000 || args.epoch>2100000000) throw new Error('invalid test clock');
      await pg.exec(`CREATE OR REPLACE FUNCTION nku_task_calendar_v1.now_epoch() RETURNS bigint LANGUAGE sql VOLATILE SET search_path='' AS $$ SELECT ${args.epoch}::bigint $$`);
      process.stdout.write('{"ok":true,"data":{}}\n'); continue;
    }
    if (op==='__test_expire_workspace__') {
      // Private test pipe, never part of deployment: exercise owner workspace
      // renewal without waiting 24 hours. No arbitrary SQL input is accepted.
      if (!/^pilot_workspace_[A-Za-z0-9_-]{24}$/.test(args.workspace_ref ?? '')) throw new Error('invalid test ref');
      await pg.query('UPDATE nku_identity_pilot_v1.workspaces SET expires_at=0 WHERE workspace_ref=$1',[args.workspace_ref]);
      process.stdout.write('{"ok":true,"data":{}}\n');
      continue;
    }
    if (op==='__test_expire_browser_session__') {
      // Test pipe only (excluded from deployment): bounded fixed SQL, never a
      // caller-supplied query. Expire the synthetic session to exercise PG.
      if (!/^[0-9a-f]{64}$/.test(args.token_hash ?? '')) throw new Error('invalid test hash');
      await pg.query("UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0 WHERE token_hash=$1",[args.token_hash]);
      process.stdout.write('{"ok":true,"data":{}}\n');
      continue;
    }
    const compatibility=op.startsWith('__competition__:');
    const notice=op.startsWith('__notice__:');
    const calendar=op.startsWith('__calendar__:');
    const personal=op.startsWith('__personal__:');
    const device=op.startsWith('__device__:');
    const agentDevice=op.startsWith('__agent_device__:');
    const sql=agentDevice ? 'SELECT public.nku_agent_device_v1_rpc($1,$2::jsonb) result' : device ? 'SELECT public.nku_browser_device_v1_rpc($1,$2::jsonb) result' : personal ? 'SELECT public.nku_personal_tasks_v1_rpc($1,$2::jsonb) result' : calendar ? 'SELECT public.nku_task_calendar_v1_rpc($1,$2::jsonb) result' : notice ? 'SELECT public.nku_notice_text_v1_rpc($1,$2::jsonb) result' : compatibility ? 'SELECT public.nku_competition_oauth_v1_rpc($1,$2::jsonb) result' : 'SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) result';
    const result=await pg.query(sql,[agentDevice ? op.slice('__agent_device__:'.length) : device ? op.slice('__device__:'.length) : personal ? op.slice('__personal__:'.length) : calendar ? op.slice('__calendar__:'.length) : notice ? op.slice('__notice__:'.length) : compatibility ? op.slice('__competition__:'.length) : op,JSON.stringify(args)]);
    process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');
  } catch {
    // Do not print submitted params/SQL/credential hashes even on test failures.
    process.stdout.write('{"driver_error":true}\n');
  }
}
await pg.close();
