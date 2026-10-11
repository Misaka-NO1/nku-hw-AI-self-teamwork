// Isolated fictional accounts only. This migration has NOT run in production.
import assert from 'node:assert/strict';
import {before,after,test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash,randomBytes} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
const hash = s=>createHash('sha256').update(s).digest('hex');
const random = ()=>hash(randomBytes(32));
const workspace = ()=>'pilot_workspace_'+randomBytes(18).toString('base64url');
let pg,oldVisitor,oldSpace;
const rpc = async(name,op,args={})=>(await pg.query(`SELECT public.${name}($1,$2::jsonb) result`,[op,JSON.stringify(args)])).rows[0].result;
const native = (op,args)=>rpc('nku_native_identity_v1_rpc',op,args);
const counts=async()=>(await pg.query('SELECT (SELECT count(*) FROM nku_identity_pilot_v1.native_identity_accounts) identities,(SELECT count(*) FROM nku_identity_pilot_v1.workspaces) spaces,(SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions) sessions')).rows[0];
const device = async()=>{
 const challenge_hash=random(),code_hash=random();
 assert.equal((await rpc('nku_agent_device_v1_rpc','start',{challenge_hash,code_hash})).ok,true);
 return {challenge_hash,code_hash};
};
before(async()=>{
 pg=new PGlite(); await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
 for(const file of ['schema.sql','competition-oauth-migration.sql','notice-text-migration.sql','task-calendar-migration.sql',
  'task-oauth-scopes-migration.sql','personal-tasks-migration.sql','persistent-auth-migration.sql','personal-schedules-migration.sql',
  'device-login-migration.sql','agent-device-binding-migration.sql','task-delete-migration.sql','browser-visitor-migration.sql'])
  await pg.exec(await readFile(new URL('../'+file,import.meta.url),'utf8'));
 await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
 await rpc('nku_identity_pilot_v1_rpc','configure_subjects',{subjects:['cloudbase_pilot_'+hash('a'),'cloudbase_pilot_'+hash('b')]});
 oldVisitor={challenge_hash:random(),code_hash:random(),subject_id:'visitor_'+random(),token_hash:random(),csrf_hash:random(),workspace_ref:workspace()};
 oldSpace=(await rpc('nku_identity_pilot_v1_rpc','visitor_begin',oldVisitor)).data.workspace_ref;
 await pg.exec(await readFile(new URL('../visitor-identity-first-migration.sql',import.meta.url),'utf8'));
 const before=(await pg.query('SELECT 0 identities,(SELECT count(*) FROM nku_identity_pilot_v1.workspaces) spaces,(SELECT count(*) FROM nku_identity_pilot_v1.browser_sessions) sessions')).rows[0];
 await pg.exec(await readFile(new URL('../native-identity-registry-migration.sql',import.meta.url),'utf8'));
 assert.deepEqual(await counts(),before);
});
after(async()=>{await pg?.close();});

test('lookup of unknown native identity never creates space or session',async()=>{
 const before=await counts();
 assert.deepEqual((await native('lookup',{identity_hash:random()})).data,{has_space:false,created:false});
 assert.deepEqual(await counts(),before);
});
test('confirmed first use creates one empty account; changed browser repeats reuse it',async()=>{
 const identity_hash=random(),one=await device(),two=await device(),before=await counts();
 const first=await native('create',{identity_hash,code_hash:one.code_hash,workspace_ref:workspace(),confirmed:true});
 assert.equal(first.ok,true);assert.equal(first.data.created,true);
 for(const code_hash of [one.code_hash,two.code_hash]) {
  const repeat=await native('create',{identity_hash,code_hash,workspace_ref:workspace(),confirmed:true});
  assert.equal(repeat.data.created,false);assert.equal(repeat.data.workspace_ref,first.data.workspace_ref);
 }
 assert.equal((await counts()).spaces,before.spaces+1);
 assert.equal((await counts()).sessions,before.sessions); // Registry does not mint credentials.
 const privateCounts=(await pg.query('SELECT (SELECT count(*) FROM nku_identity_pilot_v1.tasks t JOIN nku_identity_pilot_v1.drafts d ON d.draft_id=t.draft_id WHERE d.workspace_ref=$1) tasks,(SELECT count(*) FROM nku_identity_pilot_v1.schedules WHERE workspace_ref=$1) schedules',[first.data.workspace_ref])).rows[0];
 assert.deepEqual(privateCounts,{tasks:0,schedules:0});
});
test('separate platform accounts have separate spaces',async()=>{
 const a=await device(),b=await device();
 const first=await native('create',{identity_hash:random(),code_hash:a.code_hash,workspace_ref:workspace(),confirmed:true});
 const second=await native('create',{identity_hash:random(),code_hash:b.code_hash,workspace_ref:workspace(),confirmed:true});
 assert.notEqual(first.data.workspace_ref,second.data.workspace_ref);
});
test('cannot create over a historical browser owner or change legacy data',async()=>{
 const before=await counts();
 const result=await native('create',{identity_hash:random(),code_hash:oldVisitor.code_hash,workspace_ref:workspace(),confirmed:true});
 assert.equal(result.code,'FORBIDDEN');assert.deepEqual(await counts(),before);
 assert.equal((await rpc('nku_identity_pilot_v1_rpc','get_workspace',{session_hash:oldVisitor.token_hash})).data.workspace_ref,oldSpace);
});
test('adoption requires actual original OAuth grant, not an owner override',async()=>{
 const before=await counts();
 assert.equal((await native('adopt',{identity_hash:random(),grant_hash:random(),audience:'fictional-client',confirmed:true})).code,'AUTH_REQUIRED');
 assert.equal((await native('lookup',{identity_hash:random(),owner:'fake'})).code,'VALIDATION_ERROR');
 assert.deepEqual(await counts(),before);
});
test('original approved OAuth owner is adopted once, without a new space or account switch',async()=>{
 const identity_hash=random(),grant_hash=random(),before=await counts();
 // Test-only superuser fixture: no production bypass route or owner input.
 await pg.query("INSERT INTO nku_competition_oauth_v1.grants(token_hash,source_session_hash,audience,expires_at,scopes) VALUES($1,$2,'fictional-client',253370736000,ARRAY['demo:read','devices:bind'])",[grant_hash,oldVisitor.token_hash]);
 const args={identity_hash,grant_hash,audience:'fictional-client',confirmed:true};
 for(let i=0;i<2;i++) {
  const result=await native('adopt',args);
  assert.equal(result.ok,true);assert.equal(result.data.created,false);assert.equal(result.data.workspace_ref,oldSpace);
 }
 assert.equal((await counts()).spaces,before.spaces);
 assert.equal((await native('adopt',{...args,identity_hash:random()})).code,'FORBIDDEN');
 assert.equal((await native('adopt',{...args,audience:'wrong-client'})).code,'AUTH_REQUIRED');
 assert.equal((await native('lookup',{identity_hash})).data.workspace_ref,oldSpace);
});
test('revoked native account cannot recreate or silently restore approval',async()=>{
 const identity_hash=random(),one=await device();
 const args={identity_hash,code_hash:one.code_hash,workspace_ref:workspace(),confirmed:true};
 assert.equal((await native('create',args)).ok,true);
 await pg.query('DELETE FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=$1',['visitor_'+identity_hash]);
 const before=await counts();
 assert.equal((await native('lookup',{identity_hash})).code,'FORBIDDEN');
 assert.equal((await native('create',args)).code,'FORBIDDEN');
 assert.deepEqual(await counts(),before);
});
test('mutations need confirmation; public roles have no table/RPC access',async()=>{
 const one=await device(),before=await counts();
 assert.equal((await native('create',{identity_hash:random(),code_hash:one.code_hash,workspace_ref:workspace(),confirmed:false})).code,'CONFIRMATION_REQUIRED');
 for(const role of ['anon','authenticated']) {
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role})]);
  assert.equal((await native('lookup',{identity_hash:random()})).code,'FORBIDDEN');
  assert.equal((await pg.query("SELECT has_function_privilege($1,'public.nku_native_identity_v1_rpc(text,jsonb)','EXECUTE') allowed",[role])).rows[0].allowed,false);
 }
 await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
 assert.deepEqual(await counts(),before);
});
