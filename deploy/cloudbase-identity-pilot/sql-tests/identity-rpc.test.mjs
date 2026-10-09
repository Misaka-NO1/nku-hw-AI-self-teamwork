// Runs the real PL/pgSQL migration against embedded PostgreSQL, not a SQL mock.
// Local fixtures only; no cloud keys, accounts, network requests or real records.
import assert from 'node:assert/strict';
import { before, after, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';

const sha = s => createHash('sha256').update(s).digest('hex');
const id = prefix => prefix + randomBytes(18).toString('base64url');
const A = 'cloudbase_pilot_' + sha('fictional-env:fictional-a');
const B = 'cloudbase_pilot_' + sha('fictional-env:fictional-b');
let pg;
let fixtureHashes = {};
let a, b;
async function rpc(op,args={}) {
  const result = await pg.query('SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) result',[op,JSON.stringify(args)]);
  return result.rows[0].result;
}
async function login(subject) {
  const auth = {subject_id:subject,token_hash:sha(id('session_')),csrf_hash:sha(id('csrf_')),workspace_ref:id('pilot_workspace_')};
  const result = await rpc('login',auth);
  assert.equal(result.ok,true);
  return {session_hash:auth.token_hash,csrf_hash:auth.csrf_hash,workspace_ref:result.data.workspace_ref};
}
async function draft(owner,kind='task',fixture='notice-event.demo.json',changes={}) {
  const args={...owner,key:id('create_'),request_hash:sha(id('request_')),kind,
    payload_hash:fixtureHashes[fixture],draft_id:id('draft_'),...changes};
  return {args,result:await rpc('create_draft',args)};
}
async function save(owner,kind,fixture) {
  const created=await draft(owner,kind,fixture);
  assert.equal(created.result.ok,true);
  const confirmation_id=id('confirmation_');
  const confirm={...owner,key:id('confirm_'),request_hash:sha(id('confirm_request_')),
    draft_id:created.result.data.draft_id,revision:1,payload_hash:fixtureHashes[fixture],
    confirmation_id,confirmation_hash:sha(confirmation_id)};
  assert.equal((await rpc('confirm',confirm)).ok,true);
  const commit={...owner,kind,key:id('commit_'),request_hash:sha(id('commit_request_')),
    confirmation_hash:confirm.confirmation_hash,resource_id:id(kind+'_')};
  const result=await rpc('commit',commit);
  assert.equal(result.ok,true);
  assert.deepEqual(await rpc('commit',commit),result);
  return {created,confirm,commit,result};
}
async function grant(owner,scopes=['demo:draft','demo:read']) {
  const transaction_hash=sha(id('approval_')), code_hash=sha(id('code_'));
  const request={...owner,transaction_hash,audience:'test-school-agent',
    redirect_uri:'https://school.example.invalid/callback',scopes,
    challenge:'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',state:'fictional-state-20261002'};
  assert.equal((await rpc('authorize_start',request)).ok,true);
  assert.equal((await rpc('authorize_approve',{...owner,transaction_hash,code_hash,decision:'allow'})).ok,true);
  const exchange={code_hash,audience:request.audience,redirect_uri:request.redirect_uri,
    challenge:request.challenge,token_hash:sha(id('grant_'))};
  assert.equal((await rpc('oauth_exchange',exchange)).ok,true);
  return {request,exchange,agent:{principal_kind:'agent',grant_hash:exchange.token_hash,audience:request.audience}};
}

before(async()=>{
  pg=new PGlite();
  await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  await pg.exec(await readFile(new URL('../schema.sql',import.meta.url),'utf8'));
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  assert.equal((await rpc('configure_subjects',{subjects:[A,B]})).ok,true);
  for (const fixture of ['timetable.demo.json','notice-event.demo.json','notice-deadline.demo.json','notice-ambiguous.demo.json']) {
    const raw=JSON.parse(await readFile(new URL('../../../fixtures/'+fixture,import.meta.url),'utf8'));
    const canonical = value => value && typeof value==='object' ? Array.isArray(value) ? value.map(canonical) :
      Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])) : value;
    const hash=sha(JSON.stringify(canonical(raw)));
    fixtureHashes[fixture]=hash;
    await pg.query('INSERT INTO nku_identity_pilot_v1.fixtures VALUES($1,$2,$3::jsonb)',[hash,fixture.startsWith('timetable')?'schedule':'task',JSON.stringify(raw)]);
  }
  a=await login(A); b=await login(B);
});
after(async()=>{await pg?.close();});

test('migration uses isolated tables, RLS and only service-role RPC',async()=>{
  const rls=await pg.query("SELECT relrowsecurity FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='nku_identity_pilot_v1' AND c.relkind='r'");
  assert.equal(rls.rows.length,15);
  assert.ok(rls.rows.every(row=>row.relrowsecurity));
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'authenticated'})]);
  assert.equal((await rpc('records',a)).code,'FORBIDDEN');
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  await pg.exec('SET ROLE anon');
  await assert.rejects(rpc('probe'),/permission denied/);
  await assert.rejects(pg.query('SELECT * FROM nku_identity_pilot_v1.browser_sessions'),/permission denied/);
  await pg.exec('RESET ROLE');
});
test('unapproved subject cannot log in',async()=>{
  const result=await rpc('login',{subject_id:'cloudbase_pilot_'+sha('not-approved')});
  assert.equal(result.code,'FORBIDDEN');
});
test('shared rate limiter counts across independent calls',async()=>{
  const bucket_hash=sha(id('limit_'));
  assert.equal((await rpc('rate_limit',{bucket_hash,limit:2})).ok,true);
  assert.equal((await rpc('rate_limit',{bucket_hash,limit:2})).ok,true);
  assert.equal((await rpc('rate_limit',{bucket_hash,limit:2})).code,'RATE_LIMITED');
});
test('A fixture schedule/task save, B empty, owner workspace stable across login',async()=>{
  await save(a,'schedule','timetable.demo.json');
  await save(a,'task','notice-event.demo.json');
  const records=(await rpc('records',a)).data;
  assert.ok(records.schedule.schedule_id);
  assert.equal(records.tasks.length,1);
  const empty=(await rpc('records',b)).data;
  assert.equal(empty.schedule,null); assert.deepEqual(empty.tasks,[]);
  const relogin=await login(A);
  assert.equal(relogin.workspace_ref,a.workspace_ref);
  assert.deepEqual((await rpc('records',relogin)).data,records);
});
test('cross-owner refs and resources denied without revealing existence',async()=>{
  const mine=await save(a,'task','notice-deadline.demo.json');
  assert.equal((await rpc('list_tasks',{...b,workspace_ref:a.workspace_ref})).code,'NOT_FOUND');
  assert.equal((await rpc('get_draft',{...b,draft_id:mine.created.result.data.draft_id})).code,'NOT_FOUND');
  assert.equal((await rpc('get_task',{...b,task_id:mine.result.data.task_id})).code,'NOT_FOUND');
  assert.equal((await rpc('commit',{...mine.commit,...b})).code,'NOT_FOUND');
});
test('CSRF, ambiguous notices, fixture hashes and idempotency conflict are enforced in SQL',async()=>{
  assert.equal((await draft({...a,csrf_hash:sha('wrong')})).result.code,'FORBIDDEN');
  const made=await draft(a);
  assert.equal(made.result.ok,true);
  assert.deepEqual(await rpc('create_draft',made.args),made.result);
  assert.equal((await rpc('create_draft',{...made.args,request_hash:sha('different')})).code,'STALE_REVISION');
  assert.equal((await draft(a,'task','notice-event.demo.json',{payload_hash:sha('unknown')})).result.code,'DEMO_ONLY');
  const ambiguous=await draft(a,'task','notice-ambiguous.demo.json');
  assert.equal((await rpc('confirm',{...a,key:id('confirm_'),request_hash:sha('confirm'),draft_id:ambiguous.result.data.draft_id,
    revision:1,payload_hash:fixtureHashes['notice-ambiguous.demo.json']})).code,'CONFIRMATION_REQUIRED');
});
test('expired confirmations cannot save and wrong-kind retry never returns cached save',async()=>{
  const saved=await save(a,'task','notice-event.demo.json');
  assert.equal((await rpc('commit',{...saved.commit,kind:'schedule'})).code,'STALE_REVISION');
  const made=await draft(a); const confirmation_hash=sha(id('expire_'));
  assert.equal((await rpc('confirm',{...a,key:id('confirm_'),request_hash:sha('expiry'),draft_id:made.result.data.draft_id,
    revision:1,payload_hash:fixtureHashes['notice-event.demo.json'],confirmation_hash,confirmation_id:id('c_')})).ok,true);
  await pg.query('UPDATE nku_identity_pilot_v1.confirmations SET expires_at=1 WHERE confirmation_hash=$1',[confirmation_hash]);
  assert.equal((await rpc('commit',{...a,kind:'task',confirmation_hash,key:id('commit_'),request_hash:sha('expiry')})).code,'TOKEN_EXPIRED');
});
test('OAuth grants inherit the actual owner, never confirm/save, enforce read-only scope',async()=>{
  const ga=await grant(a), gb=await grant(b,['demo:read']);
  assert.ok((await rpc('records',ga.agent)).data.tasks.length>0);
  assert.deepEqual((await rpc('records',gb.agent)).data.tasks,[]);
  assert.equal((await draft(ga.agent)).result.ok,true);
  assert.equal((await draft(gb.agent)).result.code,'FORBIDDEN');
  assert.equal((await draft(ga.agent,'schedule','timetable.demo.json')).result.code,'FORBIDDEN');
  assert.equal((await rpc('confirm',ga.agent)).code,'FORBIDDEN');
  assert.equal((await rpc('commit',ga.agent)).code,'FORBIDDEN');
  assert.equal((await rpc('records',{...ga.agent,workspace_ref:b.workspace_ref})).code,'NOT_FOUND');
  assert.equal((await rpc('oauth_exchange',ga.exchange)).code,'AUTH_REQUIRED');
});
test('foreign consent, invalid PKCE/redirect/client and replay are rejected',async()=>{
  const transaction_hash=sha(id('approval_')); const code_hash=sha(id('code_'));
  const request={...a,transaction_hash,audience:'test-school-agent',redirect_uri:'https://school.example.invalid/callback',
    scopes:['demo:read'],challenge:'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',state:'fictional-state-20261002'};
  assert.equal((await rpc('authorize_start',request)).ok,true);
  assert.equal((await rpc('authorize_approve',{...b,transaction_hash,code_hash,decision:'allow'})).code,'FORBIDDEN');
  assert.equal((await rpc('authorize_approve',{...a,transaction_hash,code_hash,decision:'allow'})).ok,true);
  assert.equal((await rpc('authorize_approve',{...a,transaction_hash,code_hash,decision:'allow'})).code,'FORBIDDEN');
  const exchange={code_hash,audience:request.audience,redirect_uri:request.redirect_uri,challenge:request.challenge,token_hash:sha(id('g_'))};
  for(const change of [{audience:'other-client'},{redirect_uri:'https://bad.example.invalid/'},{challenge:'x'.repeat(43)}]) {
    assert.equal((await rpc('oauth_exchange',{...exchange,...change})).code,'AUTH_REQUIRED');
  }
  assert.equal((await rpc('oauth_exchange',exchange)).ok,true);
});
test('token revoke, expired session and logout invalidate access',async()=>{
  const fresh=await login(A); const g=await grant(fresh);
  assert.equal((await rpc('oauth_revoke',{token_hash:g.exchange.token_hash,audience:'other-client'})).ok,true);
  assert.equal((await rpc('records',g.agent)).ok,true);
  await rpc('oauth_revoke',{token_hash:g.exchange.token_hash,audience:'test-school-agent'});
  assert.equal((await rpc('records',g.agent)).code,'FORBIDDEN');
  const g2=await grant(fresh);
  assert.equal((await rpc('logout',fresh)).ok,true);
  assert.equal((await rpc('records',g2.agent)).code,'AUTH_REQUIRED');
  const expired=await login(A);
  await pg.query('UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=1 WHERE token_hash=$1',[expired.session_hash]);
  assert.equal((await rpc('records',expired)).code,'AUTH_REQUIRED');
});
test('import tickets are owner scoped, schedule-only and one-use',async()=>{
  const ticket_hash=sha(id('ticket_')); const ticket_id=id('ticket_');
  const result=await rpc('import_ticket',{...a,key:id('ticket_key_'),request_hash:sha('ticket'),purpose:'schedule_import',ticket_hash,ticket_id});
  assert.equal(result.ok,true);
  const actor={principal_kind:'import_ticket',ticket_hash};
  assert.equal((await rpc('records',actor)).code,'AUTH_REQUIRED');
  assert.equal((await draft(actor,'task','notice-event.demo.json')).result.code,'AUTH_REQUIRED');
  const made=await draft(actor,'schedule','timetable.demo.json');
  assert.equal(made.result.ok,true);
  assert.deepEqual(await rpc('create_draft',made.args),made.result);
  assert.equal((await draft(actor,'schedule','timetable.demo.json')).result.code,'TOKEN_EXPIRED');
});
test('removing approval invalidates live grants and browser sessions',async()=>{
  const g=await grant(a);
  await pg.query('DELETE FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=$1',[A]);
  assert.equal((await rpc('records',a)).code,'AUTH_REQUIRED');
  assert.equal((await rpc('records',g.agent)).code,'AUTH_REQUIRED');
  await rpc('configure_subjects',{subjects:[A,B]});
});
test('configured whitelist removal cannot resurrect old sessions when user is reapproved',async()=>{
  const fresh=await login(A); const g=await grant(fresh);
  const other='cloudbase_pilot_'+sha('fictional-other-owner');
  assert.equal((await rpc('configure_subjects',{subjects:[other,B]})).ok,true);
  assert.equal((await rpc('records',fresh)).code,'AUTH_REQUIRED');
  assert.equal((await rpc('configure_subjects',{subjects:[A,B]})).ok,true);
  assert.equal((await rpc('records',fresh)).code,'AUTH_REQUIRED');
  assert.equal((await rpc('records',g.agent)).code,'AUTH_REQUIRED');
});
