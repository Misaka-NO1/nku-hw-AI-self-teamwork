import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
const sha=s=>createHash('sha256').update(s).digest('hex');
const id=p=>p+randomBytes(18).toString('base64url');
let pg,owners;
const call=async(name,op,args)=>(await pg.query(`SELECT public.${name}($1,$2::jsonb) result`,[op,JSON.stringify(args)])).rows[0].result;
const identity=(op,args={})=>call('nku_identity_pilot_v1_rpc',op,args);
const device=(op,args={})=>call('nku_browser_device_v1_rpc',op,args);
async function login(index=0,persistent=false){
 const args={subject_id:owners[index],token_hash:sha(id('session')),csrf_hash:sha(id('csrf')),workspace_ref:id('pilot_workspace_')};
 if(persistent) Object.assign(args,{previous_session_hash:sha(''),persistent:true});
 const result=await identity('login',args);assert.equal(result.ok,true);
 return {session_hash:args.token_hash,csrf_hash:args.csrf_hash,workspace_ref:result.data.workspace_ref,expiry:result.data.expires_epoch};
}
async function start(){const args={challenge_hash:sha(id('challenge')),code_hash:sha(id('display-code'))};assert.equal((await device('start',args)).ok,true);return args;}
async function review(source,pending){const args={session_hash:source.session_hash,csrf_hash:source.csrf_hash,code_hash:pending.code_hash,receipt_hash:sha(id('receipt'))};assert.equal((await device('review',args)).ok,true);return args;}
async function approve(reviewArgs){assert.equal((await device('approve',{...reviewArgs,confirm_device:true})).ok,true);}
const claimArgs=p=>({challenge_hash:p.challenge_hash,token_hash:sha(id('device-session')),csrf_hash:sha(id('device-csrf'))});
before(async()=>{
 pg=new PGlite();await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
 for(const file of ['schema.sql','competition-oauth-migration.sql','persistent-auth-migration.sql','device-login-migration.sql'])
  await pg.exec(await readFile(new URL('../'+file,import.meta.url),'utf8'));
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"service_role\"}',false)");
 owners=['cloudbase_pilot_'+sha('device-owner-a'),'cloudbase_pilot_'+sha('device-owner-b')];
 assert.equal((await identity('configure_subjects',{subjects:owners})).ok,true);
});
after(async()=>{await pg.close();});
test('new device binds only after explicit source review and independent browser proof',async()=>{
 const a=await login(),b=await login(1),p=await start(),claim=claimArgs(p);
 assert.equal((await device('claim',claim)).data.status,'pending');
 const r=await review(a,p);
 assert.equal((await device('claim',claim)).data.status,'pending');
 assert.equal((await device('approve',{...r,confirm_device:false})).code,'CONFIRMATION_REQUIRED');
 assert.equal((await device('approve',{...r,session_hash:b.session_hash,csrf_hash:b.csrf_hash,confirm_device:true})).code,'CONFIRMATION_REQUIRED');
 await approve(r);
 for(const substitute of [p.code_hash,r.receipt_hash,sha('guess')])
  assert.equal((await device('claim',{...claim,challenge_hash:substitute})).code,'TOKEN_EXPIRED');
 const result=await device('claim',claim);assert.equal(result.ok,true);assert.equal(result.data.workspace_ref,a.workspace_ref);
 const row=(await pg.query('SELECT * FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=$1',[claim.token_hash])).rows[0];
 assert.equal(row.owner_subject_id,owners[0]);assert.equal(row.device_source_session_hash,a.session_hash);
 assert.equal((await identity('get_workspace',{session_hash:claim.token_hash})).ok,true);
 assert.equal((await identity('get_workspace',{session_hash:claim.token_hash,workspace_ref:b.workspace_ref})).code,'NOT_FOUND');
 assert.equal((await device('claim',claimArgs(p))).code,'TOKEN_EXPIRED');
 assert.equal((await device('approve',{...r,confirm_device:true})).code,'TOKEN_EXPIRED');
 const next=await start();assert.equal((await device('review',{session_hash:claim.token_hash,csrf_hash:claim.csrf_hash,code_hash:next.code_hash,receipt_hash:sha(id('receipt'))})).code,'FORBIDDEN');
});
test('only the same authenticated browser and CSRF may approve; identity fields are rejected',async()=>{
 const a=await login(),p=await start();
 const args={session_hash:a.session_hash,csrf_hash:a.csrf_hash,code_hash:p.code_hash,receipt_hash:sha(id('receipt'))};
 assert.equal((await device('review',{...args,csrf_hash:sha('wrong')})).code,'FORBIDDEN');
 for(const key of ['SYS_USERID','owner_subject_id','workspace_ref','audience','scopes'])
  assert.equal((await device('review',{...args,[key]:'injected'})).code,'VALIDATION_ERROR');
 const r=await review(a,p);
 assert.equal((await device('approve',{...r,confirm_device:'true'})).code,'CONFIRMATION_REQUIRED');
 assert.equal((await device('approve',{...r,receipt_hash:sha('wrong'),confirm_device:true})).code,'CONFIRMATION_REQUIRED');
});
test('pending and reviewed enrollments expire without creating a session',async()=>{
 const a=await login(),p=await start(),r=await review(a,p),claim=claimArgs(p);
 await pg.query('UPDATE nku_identity_pilot_v1.device_enrollments SET receipt_expires_at=0 WHERE challenge_hash=$1',[p.challenge_hash]);
 assert.equal((await device('approve',{...r,confirm_device:true})).code,'CONFIRMATION_REQUIRED');
 await pg.query('UPDATE nku_identity_pilot_v1.device_enrollments SET expires_at=0 WHERE challenge_hash=$1',[p.challenge_hash]);
 assert.equal((await device('claim',claim)).code,'TOKEN_EXPIRED');
 assert.equal((await pg.query('SELECT count(*) n FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=$1',[claim.token_hash])).rows[0].n,0);
});
test('device duration inherits source expiry; source logout revokes the device without deleting owner data',async()=>{
 for(const persistent of [false,true]){
  const a=await login(0,persistent),p=await start();await approve(await review(a,p));
  const claim=claimArgs(p),bound=await device('claim',claim);assert.equal(bound.ok,true);
  const source=(await pg.query('SELECT expires_at FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=$1',[a.session_hash])).rows[0];
  assert.equal(bound.data.expires_epoch,source.expires_at);
  assert.equal((await identity('logout',{session_hash:a.session_hash,csrf_hash:a.csrf_hash})).ok,true);
  assert.equal((await identity('get_workspace',{session_hash:claim.token_hash})).code,'AUTH_REQUIRED');
  assert.equal((await pg.query('SELECT count(*) n FROM nku_identity_pilot_v1.workspaces WHERE workspace_ref=$1',[a.workspace_ref])).rows[0].n,1);
 }
});
test('logout of just the paired device does not log out the source browser',async()=>{
 const a=await login(),p=await start();await approve(await review(a,p));const claim=claimArgs(p);await device('claim',claim);
 assert.equal((await identity('logout',{session_hash:claim.token_hash,csrf_hash:claim.csrf_hash})).ok,true);
 assert.equal((await identity('get_workspace',{session_hash:a.session_hash})).ok,true);
});
test('source expiry shortening also expires its child without extending an older child',async()=>{
 const a=await login(),p=await start();await approve(await review(a,p));const claim=claimArgs(p);await device('claim',claim);
 await pg.query('UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0 WHERE token_hash=$1',[a.session_hash]);
 assert.equal((await identity('get_workspace',{session_hash:claim.token_hash})).code,'AUTH_REQUIRED');
 const rows=await pg.query('SELECT expires_at FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=$1',[claim.token_hash]);assert.equal(rows.rows[0].expires_at,0);
});
test('existing login remains compatible and SQL tables are not available to browser roles',async()=>{
 await login();
 for(const role of ['anon','authenticated','service_role']){
  const r=await pg.query("SELECT has_table_privilege($1,'nku_identity_pilot_v1.device_enrollments','SELECT') permitted",[role]);assert.equal(r.rows[0].permitted,false);
 }
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"authenticated\"}',false)");
 assert.equal((await device('start',{challenge_hash:sha('x'),code_hash:sha('y')})).code,'FORBIDDEN');
});
