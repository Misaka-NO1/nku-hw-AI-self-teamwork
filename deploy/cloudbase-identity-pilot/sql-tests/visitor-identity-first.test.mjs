// Identity-first upgrade: isolated PG, no production users or credentials.
import assert from 'node:assert/strict';
import { before, after, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
const sha = value => createHash('sha256').update(value).digest('hex');
const fresh = () => ({challenge_hash:sha(randomBytes(32)),code_hash:sha(randomBytes(32)),
 subject_id:'visitor_'+sha(randomBytes(32)),token_hash:sha(randomBytes(32)),csrf_hash:sha(randomBytes(32)),
 workspace_ref:'pilot_workspace_'+randomBytes(18).toString('base64url')});
let pg, known, original;
const rpc = async(op,args={}) => (await pg.query('SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) result',[op,JSON.stringify(args)])).rows[0].result;
const counts = async()=> (await pg.query('SELECT (SELECT count(*) FROM nku_identity_pilot_v1.browser_visitors) visitors,(SELECT count(*) FROM nku_identity_pilot_v1.owner_workspaces) owners,(SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions) sessions')).rows[0];
before(async()=>{
 pg=new PGlite();await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
 for(const file of ['schema.sql','competition-oauth-migration.sql','notice-text-migration.sql',
  'task-calendar-migration.sql','task-oauth-scopes-migration.sql','personal-tasks-migration.sql',
  'persistent-auth-migration.sql','personal-schedules-migration.sql','device-login-migration.sql',
  'agent-device-binding-migration.sql','task-delete-migration.sql','browser-visitor-migration.sql']) {
  await pg.exec(await readFile(new URL('../'+file,import.meta.url),'utf8'));
 }
 await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
 await rpc('configure_subjects',{subjects:['cloudbase_pilot_'+sha('fictional-a'),'cloudbase_pilot_'+sha('fictional-b')]});
 known=fresh();original=await rpc('visitor_begin',known);assert.equal(original.ok,true);
 const before=await counts();
 await pg.exec(await readFile(new URL('../visitor-identity-first-migration.sql',import.meta.url),'utf8'));
 assert.deepEqual(await counts(),before); // Upgrade does not touch existing records.
});
after(async()=>{await pg?.close();});
test('identity-first probe is required and old enrollment RPC has no role bypass',async()=>{
 assert.deepEqual((await rpc('visitor_probe')).data,{schema_version:'browser-visitor-identity-first-v2'});
 for(const role of ['anon','authenticated','service_role']) {
  assert.equal((await pg.query("SELECT has_function_privilege($1,'public.nku_identity_pilot_v1_before_identity_first_rpc(text,jsonb)','EXECUTE') ok",[role])).rows[0].ok,false);
 }
});
test('new/unknown browser cannot create another owner even on repeated or concurrent calls',async()=>{
 const before=await counts(), unknown=fresh();
 const results=await Promise.all(Array.from({length:4},()=>rpc('visitor_begin',{...fresh(),challenge_hash:unknown.challenge_hash,code_hash:unknown.code_hash})));
 for(const result of results) assert.equal(result.code,'AUTH_REQUIRED');
 assert.deepEqual(await counts(),before);
});
test('private proof resumes historical owner, ignoring a newly proposed account/workspace',async()=>{
 const before=await counts();
 const result=await rpc('visitor_begin',{...fresh(),challenge_hash:known.challenge_hash,code_hash:known.code_hash});
 assert.equal(result.ok,true);assert.equal(result.data.workspace_ref,original.data.workspace_ref);
 const after=await counts();assert.equal(after.visitors,before.visitors);assert.equal(after.owners,before.owners);
});
test('copied public code and wrong code cannot resume or enroll',async()=>{
 const before=await counts();
 assert.equal((await rpc('visitor_begin',{...fresh(),challenge_hash:known.code_hash})).code,'AUTH_REQUIRED');
 assert.equal((await rpc('visitor_begin',{...fresh(),challenge_hash:known.challenge_hash})).code,'STALE_REVISION');
 assert.deepEqual(await counts(),before);
});
test('anonymous/authenticated roles cannot run resume',async()=>{
 for(const role of ['anon','authenticated']) {
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role})]);
  assert.equal((await rpc('visitor_begin',known)).code,'FORBIDDEN');
 }
 await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
});
test('invalid shapes and owner overrides cannot enroll',async()=>{
 const before=await counts();
 for(const args of [null,[],{}, {...fresh(),owner:'other'}, {...fresh(),challenge_hash:'DEV-PUBLIC'}])
  assert.equal((await rpc('visitor_begin',args)).code,'VALIDATION_ERROR');
 assert.deepEqual(await counts(),before);
});
