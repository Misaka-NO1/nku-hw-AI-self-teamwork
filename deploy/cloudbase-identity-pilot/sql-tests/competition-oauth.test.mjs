// Additive demo compatibility SQL permission/validation tests, no cloud keys.
import assert from 'node:assert/strict';
import {before,after,test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
let pg,session;
const sha=s=>createHash('sha256').update(s).digest('hex');
const callback='https://coze.nankai.edu.cn/product/llm/info/oauth';
async function rpc(op,args={}) {
  return (await pg.query('SELECT public.nku_competition_oauth_v1_rpc($1,$2::jsonb) result',[op,JSON.stringify(args)])).rows[0].result;
}
before(async()=>{
  pg=new PGlite();
  await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  await pg.exec(await readFile(new URL('../schema.sql',import.meta.url),'utf8'));
  await pg.exec(await readFile(new URL('../competition-oauth-migration.sql',import.meta.url),'utf8'));
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  const a='cloudbase_pilot_'+sha('fake-a'),b='cloudbase_pilot_'+sha('fake-b');
  await pg.query("SELECT public.nku_identity_pilot_v1_rpc('configure_subjects',$1::jsonb)",[JSON.stringify({subjects:[a,b]})]);
  session=sha('synthetic-session');
  await pg.query("SELECT public.nku_identity_pilot_v1_rpc('login',$1::jsonb)",[
    JSON.stringify({subject_id:a,token_hash:session,csrf_hash:sha('synthetic-csrf'),workspace_ref:'pilot_workspace_'+'a'.repeat(24)})]);
});
after(async()=>pg.close());
test('only new three RLS tables, old 15 tables unchanged; client roles cannot execute',async()=>{
  const rows=(await pg.query("SELECT schemaname,count(*)::int n,bool_and(rowsecurity) rls FROM pg_tables WHERE schemaname IN ('nku_identity_pilot_v1','nku_competition_oauth_v1') GROUP BY schemaname")).rows;
  assert.equal(rows.find(x=>x.schemaname==='nku_identity_pilot_v1').n,15);
  assert.deepEqual(rows.find(x=>x.schemaname==='nku_competition_oauth_v1'),{schemaname:'nku_competition_oauth_v1',n:3,rls:true});
  for(const role of ['anon','authenticated']) {
    const x=(await pg.query("SELECT has_function_privilege($1,'public.nku_competition_oauth_v1_rpc(text,jsonb)','EXECUTE') allowed",[role])).rows[0];
    assert.equal(x.allowed,false);
  }
});
test('missing service role is refused even for probe',async()=>{
  await pg.query("SELECT set_config('request.jwt.claims','{}',false)");
  assert.equal((await rpc('probe')).code,'FORBIDDEN');
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
});
test('read RPC denies owner overrides, null hashes, arbitrary operations and missing grant',async()=>{
  assert.equal((await rpc('records',{grant_hash:sha('none'),audience:'test-school-agent',owner:'fake-a'})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('records',{grant_hash:null,audience:'test-school-agent'})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('commit',{})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('records',{grant_hash:sha('none'),audience:'test-school-agent'})).code,'AUTH_REQUIRED');
});
test('exact callback and bounded state without PostgreSQL repetition overflow',async()=>{
  const args={session_hash:session,transaction_hash:sha('valid-txn'),audience:'test-school-agent',redirect_uri:callback,state:'x'.repeat(256)};
  assert.equal((await rpc('authorize_start',{...args,redirect_uri:'https://attacker.invalid'})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('authorize_start',{...args,state:'x'.repeat(257)})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('authorize_start',args)).ok,true);
});
test('expired consent/code rejected; no caller-selected scopes or write operation',async()=>{
  const transaction_hash=sha('expiry-txn'),code_hash=sha('expiry-code');
  assert.equal((await rpc('authorize_start',{session_hash:session,transaction_hash,audience:'test-school-agent',redirect_uri:callback,state:'a123456789',scopes:['demo:draft']})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('authorize_start',{session_hash:session,transaction_hash,audience:'test-school-agent',redirect_uri:callback,state:'a123456789'})).ok,true);
  assert.equal((await rpc('authorize_approve',{session_hash:session,transaction_hash,code_hash,decision:'allow'})).ok,true);
  await pg.query('UPDATE nku_competition_oauth_v1.codes SET expires_at=0 WHERE code_hash=$1',[code_hash]);
  assert.equal((await rpc('exchange',{code_hash,audience:'test-school-agent',redirect_uri:callback,token_hash:sha('unused-token')})).code,'AUTH_REQUIRED');
});
