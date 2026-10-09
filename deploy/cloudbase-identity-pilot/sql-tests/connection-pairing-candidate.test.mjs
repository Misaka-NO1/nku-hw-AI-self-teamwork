// Real embedded PostgreSQL; offline candidate, not deployed or double-connection cloud evidence.
import assert from 'node:assert/strict';
import {before,after,test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash,randomBytes} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';

const sha=s=>createHash('sha256').update(s).digest('hex');
const hash=()=>sha(randomBytes(32).toString('hex'));
const audience='offline-connection-pairing-test';
const A='cloudbase_pilot_'+sha('offline-a'),B='cloudbase_pilot_'+sha('offline-b');
let pg,a,b,taskA,taskB;
const call=async (name,op,args)=> (await pg.query(`SELECT public.${name}($1,$2::jsonb) result`,[op,JSON.stringify(args)])).rows[0].result;
const identity=(op,args={})=>call('nku_identity_pilot_v1_rpc',op,args);
const pairing=(op,args={})=>call('nku_connection_pairing_candidate_v1_rpc',op,args);
async function login(owner){
  const token_hash=hash(),csrf_hash=hash();
  const result=await identity('login',{subject_id:owner,token_hash,csrf_hash,workspace_ref:'pilot_workspace_'+randomBytes(18).toString('base64url')});
  assert.equal(result.ok,true);
  return {session_hash:token_hash,csrf_hash};
}
async function connection(){
  const code_hash=hash(),token_hash=hash(),user_code_hash=hash();
  assert.equal((await pairing('bootstrap',{audience,code_hash})).ok,true);
  const result=await pairing('exchange',{audience,code_hash,token_hash,user_code_hash});
  assert.equal(result.ok,true);
  return {code_hash,token_hash,user_code_hash};
}
async function review(owner,c){
  const receipt_hash=hash();
  const result=await pairing('review',{...owner,user_code_hash:c.user_code_hash,receipt_hash});
  assert.equal(result.ok,true);
  return receipt_hash;
}
async function approve(owner,c,receipt_hash,extra={}){
  return pairing('approve',{...owner,receipt_hash,user_code_hash:c.user_code_hash,confirm_same_agent:true,confirm_read:true,...extra});
}
async function saveFixture(owner,name){
  const canonical=v=>v&&typeof v==='object'?Array.isArray(v)?v.map(canonical):Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
  const raw=JSON.parse(await readFile(new URL('../../../fixtures/'+name,import.meta.url),'utf8'));
  const payload_hash=sha(JSON.stringify(canonical(raw)));
  await pg.query("INSERT INTO nku_identity_pilot_v1.fixtures VALUES($1,'task',$2::jsonb)",[payload_hash,JSON.stringify(raw)]);
  const draft_id='draft_'+randomBytes(18).toString('base64url');
  assert.equal((await identity('create_draft',{...owner,key:'create_'+hash(),request_hash:hash(),kind:'task',payload_hash,draft_id})).ok,true);
  const confirmation_hash=hash();
  assert.equal((await identity('confirm',{...owner,key:'confirm_'+hash(),request_hash:hash(),draft_id,revision:1,payload_hash,confirmation_hash,confirmation_id:'confirmation_'+hash()})).ok,true);
  const task_id='task_'+randomBytes(18).toString('base64url');
  assert.equal((await identity('commit',{...owner,key:'commit_'+hash(),request_hash:hash(),kind:'task',confirmation_hash,resource_id:task_id})).ok,true);
  return task_id;
}

before(async()=>{
  pg=new PGlite();
  await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  await pg.exec(await readFile(new URL('../schema.sql',import.meta.url),'utf8'));
  await pg.exec(await readFile(new URL('../../connection-pairing-candidate/schema.sql',import.meta.url),'utf8'));
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  assert.equal((await identity('configure_subjects',{subjects:[A,B]})).ok,true);
  a=await login(A); b=await login(B);
  taskA=await saveFixture(a,'notice-event.demo.json');
  taskB=await saveFixture(b,'notice-deadline.demo.json');
});
after(async()=>{await pg?.close();});

test('new schema defaults disabled, has RLS, cannot be queried or executed by anon/authenticated',async()=>{
  assert.equal((await pairing('bootstrap',{audience,code_hash:hash()})).code,'FORBIDDEN');
  const rows=(await pg.query("SELECT relrowsecurity FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='nku_connection_pairing_candidate_v1' AND c.relkind='r'")).rows;
  assert.equal(rows.length,6); assert.ok(rows.every(r=>r.relrowsecurity));
  for(const role of ['anon','authenticated']){
    await pg.exec('SET ROLE '+role);
    await assert.rejects(pairing('probe'),/permission denied/);
    await assert.rejects(pg.query('SELECT * FROM nku_connection_pairing_candidate_v1.connections'),/permission denied/);
    await pg.exec('RESET ROLE');
  }
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'authenticated'})]);
  assert.equal((await pairing('probe')).code,'FORBIDDEN');
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  assert.equal((await pairing('configure',{audience,enabled:true})).ok,true);
});

test('anonymous bootstrap has no identity; exchange is one-use and pending cannot return records',async()=>{
  const c=await connection();
  const result=await pairing('records',{audience,token_hash:c.token_hash});
  assert.equal(result.data.status,'pairing_required');
  assert.deepEqual(Object.keys(result.data).sort(),['expires_epoch','status']);
  assert.equal((await pairing('exchange',{audience,...c})).code,'AUTH_REQUIRED');
  const stored=(await pg.query('SELECT owner_subject_id,source_session_hash FROM nku_connection_pairing_candidate_v1.connections WHERE token_hash=$1',[c.token_hash])).rows[0];
  assert.equal(stored.owner_subject_id,null); assert.equal(stored.source_session_hash,null);
});

test('no caller identity overrides, invalid hash types, arbitrary ops or wrong audience',async()=>{
  const c=await connection();
  for(const extra of ['owner_subject_id','workspace_ref','SYS_USERID','principal_kind']){
    assert.equal((await pairing('records',{audience,token_hash:c.token_hash,[extra]:'fictional'})).code,'VALIDATION_ERROR');
  }
  assert.equal((await pairing('records',{audience,token_hash:null})).code,'VALIDATION_ERROR');
  assert.equal((await pairing('records',{audience,token_hash:123})).code,'VALIDATION_ERROR');
  assert.equal((await pairing('commit',{})).code,'VALIDATION_ERROR');
  assert.equal((await pairing('records',{audience:'other-client',token_hash:c.token_hash})).code,'FORBIDDEN');
});

test('verified session, matching CSRF, explicit booleans and same session review required',async()=>{
  const c=await connection();
  assert.equal((await pairing('review',{session_hash:hash(),csrf_hash:hash(),user_code_hash:c.user_code_hash,receipt_hash:hash()})).code,'AUTH_REQUIRED');
  assert.equal((await pairing('review',{...a,csrf_hash:hash(),user_code_hash:c.user_code_hash,receipt_hash:hash()})).code,'FORBIDDEN');
  const receipt_hash=await review(a,c);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).data.status,'pairing_required');
  assert.equal((await approve(b,c,receipt_hash)).code,'FORBIDDEN');
  assert.equal((await approve(a,c,receipt_hash,{confirm_read:'true'})).code,'CONFIRMATION_REQUIRED');
  assert.equal((await approve(a,c,receipt_hash,{user_code_hash:hash()})).code,'STALE_REVISION');
  assert.equal((await approve(a,c,receipt_hash)).ok,true);
  assert.equal((await approve(a,c,receipt_hash)).code,'FORBIDDEN');
});

test('paired grant derives actual owner; cannot rebind and never writes identity grant tables',async()=>{
  const c=await connection();
  const reviewA=await review(a,c),reviewB=await review(b,c);
  assert.equal((await approve(a,c,reviewA)).ok,true);
  assert.equal((await approve(b,c,reviewB)).code,'STALE_REVISION');
  const own=(await pairing('records',{audience,token_hash:c.token_hash}));
  assert.deepEqual(own,await identity('records',a));
  assert.equal(own.data.tasks.length,1);
  assert.equal(own.data.tasks[0].task_id,taskA);
  assert.notEqual(own.data.tasks[0].task_id,taskB);
  const stored=(await pg.query('SELECT owner_subject_id FROM nku_connection_pairing_candidate_v1.connections WHERE token_hash=$1',[c.token_hash])).rows[0];
  assert.equal(stored.owner_subject_id,A);
  assert.equal((await pg.query('SELECT count(*)::int n FROM nku_identity_pilot_v1.oauth_grants')).rows[0].n,0);
});

test('revocation, expired pairing and review reject reuse',async()=>{
  const c=await connection();
  const receipt_hash=await review(a,c);
  await pg.query('UPDATE nku_connection_pairing_candidate_v1.reviews SET expires_at=0 WHERE receipt_hash=$1',[receipt_hash]);
  assert.equal((await approve(a,c,receipt_hash)).code,'FORBIDDEN');
  await pg.query('UPDATE nku_connection_pairing_candidate_v1.connections SET pairing_expires_at=0 WHERE token_hash=$1',[c.token_hash]);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).code,'TOKEN_EXPIRED');
  assert.equal((await pairing('revoke',{audience,token_hash:c.token_hash})).ok,true);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).code,'AUTH_REQUIRED');
});

test('logout deletes source session and delegated read stops immediately',async()=>{
  const owner=await login(B),c=await connection();
  assert.equal((await approve(owner,c,await review(owner,c))).ok,true);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).ok,true);
  assert.equal((await identity('logout',owner)).ok,true);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).code,'AUTH_REQUIRED');
});

test('source session expiry rejects delegated read without borrowing another active session',async()=>{
  const owner=await login(B),c=await connection();
  assert.equal((await approve(owner,c,await review(owner,c))).ok,true);
  await pg.query('UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0 WHERE token_hash=$1',[owner.session_hash]);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).code,'AUTH_REQUIRED');
  assert.equal((await identity('records',b)).ok,true);
});

test('failed guesses are counted per owner despite changing login session',async()=>{
  for(let i=0;i<5;i++) await pairing('review',{...b,user_code_hash:hash(),receipt_hash:hash()});
  const newer=await login(B);
  assert.equal((await pairing('review',{...newer,user_code_hash:hash(),receipt_hash:hash()})).code,'RATE_LIMITED');
});

test('runtime kill switch denies pending and previously paired connections',async()=>{
  const c=await connection();
  assert.equal((await pairing('configure',{audience,enabled:false})).ok,true);
  assert.equal((await pairing('records',{audience,token_hash:c.token_hash})).code,'FORBIDDEN');
});
