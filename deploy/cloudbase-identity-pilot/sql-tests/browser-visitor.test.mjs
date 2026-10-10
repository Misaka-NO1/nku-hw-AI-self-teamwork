// Local embedded PostgreSQL only: no cloud credentials, users or network.
import assert from 'node:assert/strict';
import { before, after, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
const sha = value => createHash('sha256').update(value).digest('hex');
const id = prefix => prefix + randomBytes(18).toString('base64url');
const registered = ['cloudbase_pilot_' + sha('visitor-test-a'), 'cloudbase_pilot_' + sha('visitor-test-b')];
let pg;
const rpc = async (op, args = {}) => (await pg.query(
  'SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) result', [op, JSON.stringify(args)])).rows[0].result;
const fresh = () => ({challenge_hash:sha(id('device')),code_hash:sha(id('code')),
  subject_id:'visitor_' + sha(id('owner')),token_hash:sha(id('session')),csrf_hash:sha(id('csrf')),
  workspace_ref:id('pilot_workspace_')});
before(async () => {
  pg = new PGlite();
  await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  for (const file of ['schema.sql','competition-oauth-migration.sql','notice-text-migration.sql',
    'task-calendar-migration.sql','task-oauth-scopes-migration.sql','personal-tasks-migration.sql',
    'persistent-auth-migration.sql','personal-schedules-migration.sql','device-login-migration.sql',
    'agent-device-binding-migration.sql','task-delete-migration.sql','browser-visitor-migration.sql']) {
    await pg.exec(await readFile(new URL('../' + file, import.meta.url), 'utf8'));
  }
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)", [JSON.stringify({role:'service_role'})]);
  assert.equal((await rpc('configure_subjects',{subjects:registered})).ok, true);
});
after(async () => { await pg?.close(); });
test('visitor table uses RLS, no direct role access and no anonymous RPC', async () => {
  assert.equal((await pg.query("SELECT relrowsecurity FROM pg_class WHERE oid='nku_identity_pilot_v1.browser_visitors'::regclass")).rows[0].relrowsecurity, true);
  for (const role of ['anon','authenticated','service_role']) {
    for (const privilege of ['SELECT','INSERT','UPDATE','DELETE']) {
      assert.equal((await pg.query("SELECT has_table_privilege($1,'nku_identity_pilot_v1.browser_visitors',$2) ok",[role,privilege])).rows[0].ok, false);
    }
    assert.equal((await pg.query("SELECT has_function_privilege($1,'public.nku_identity_pilot_v1_before_visitors_rpc(text,jsonb)','EXECUTE') ok",[role])).rows[0].ok, false);
  }
  for (const role of ['anon','authenticated']) {
    assert.equal((await pg.query("SELECT has_function_privilege($1,'public.nku_identity_pilot_v1_rpc(text,jsonb)','EXECUTE') ok",[role])).rows[0].ok, false);
    await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role})]);
    assert.equal((await rpc('visitor_begin',fresh())).code, 'FORBIDDEN');
  }
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
});
test('independent visitors, explicit resume and restart roster synchronization preserve ownership', async () => {
  const a=fresh(), b=fresh();
  const first=await rpc('visitor_begin',a), second=await rpc('visitor_begin',b);
  assert.equal(first.ok,true); assert.equal(second.ok,true);
  assert.notEqual(first.data.workspace_ref,second.data.workspace_ref);
  assert.equal((await rpc('visitor_status',{session_hash:a.token_hash})).data.visitor,true);
  const resumed=await rpc('visitor_begin',{...fresh(),challenge_hash:a.challenge_hash,code_hash:a.code_hash});
  assert.equal(resumed.data.workspace_ref,first.data.workspace_ref);
  assert.equal((await rpc('configure_subjects',{subjects:registered})).ok,true);
  assert.equal((await rpc('get_workspace',{session_hash:a.token_hash})).data.workspace_ref,first.data.workspace_ref);
  const copiedCode=await rpc('visitor_begin',{...fresh(),challenge_hash:a.code_hash});
  assert.equal(copiedCode.ok,true);
  assert.notEqual(copiedCode.data.workspace_ref,first.data.workspace_ref);
});
test('already registered device cannot become a visitor or change its owner', async () => {
  const args=fresh();
  const login={subject_id:registered[0],token_hash:sha(id('registered')),csrf_hash:sha(id('csrf')),
    workspace_ref:id('pilot_workspace_'),previous_session_hash:sha(''),persistent:true};
  assert.equal((await rpc('login',login)).ok,true);
  const device=(await pg.query('SELECT public.nku_agent_device_v1_rpc($1,$2::jsonb) result',
    ['register',JSON.stringify({challenge_hash:args.challenge_hash,code_hash:args.code_hash,session_hash:login.token_hash})])).rows[0].result;
  assert.equal(device.ok,true);
  assert.equal((await rpc('visitor_begin',args)).code,'STALE_REVISION');
  assert.equal((await pg.query('SELECT count(*) n FROM nku_identity_pilot_v1.browser_visitors WHERE challenge_hash=$1',[args.challenge_hash])).rows[0].n,0);
  assert.equal((await rpc('get_workspace',{session_hash:login.token_hash})).data.workspace_ref,login.workspace_ref);
});
test('visitor active session cap is enforced atomically', async () => {
  const a=fresh();
  for(let n=0;n<20;n++) {
    assert.equal((await rpc('visitor_begin',{...fresh(),challenge_hash:a.challenge_hash,code_hash:a.code_hash})).ok,true);
  }
  assert.equal((await rpc('visitor_begin',{...fresh(),challenge_hash:a.challenge_hash,code_hash:a.code_hash})).code,'RATE_LIMITED');
});
