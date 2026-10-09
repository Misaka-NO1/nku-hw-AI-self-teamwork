import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
const sha=s=>createHash('sha256').update(s).digest('hex');
const id=p=>p+randomBytes(18).toString('base64url');
let pg, owners;
const call=async(name,op,args={})=>(await pg.query(`SELECT public.${name}($1,$2::jsonb) result`,[op,JSON.stringify(args)])).rows[0].result;
const identity=(op,args)=>call('nku_identity_pilot_v1_rpc',op,args);
const oauth=(op,args)=>call('nku_competition_oauth_v1_rpc',op,args);
const device=(op,args)=>call('nku_agent_device_v1_rpc',op,args);
before(async()=>{
 pg=new PGlite();await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
 for(const file of ['schema.sql','competition-oauth-migration.sql','task-oauth-scopes-migration.sql','persistent-auth-migration.sql','device-login-migration.sql','agent-device-binding-migration.sql'])
  await pg.exec(await readFile(new URL('../'+file,import.meta.url),'utf8'));
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"service_role\"}',false)");
 owners=['cloudbase_pilot_'+sha('fixed-a'),'cloudbase_pilot_'+sha('fixed-b')];
 assert.equal((await identity('configure_subjects',{subjects:owners})).ok,true);
});
after(async()=>pg.close());
async function setup(scope='demo:read devices:bind'){
 const login={subject_id:owners[0],token_hash:sha(id('session')),csrf_hash:sha(id('csrf')),workspace_ref:id('pilot_workspace_'),previous_session_hash:sha(''),persistent:true};
 assert.equal((await identity('login',login)).ok,true);
 const request={session_hash:login.token_hash,transaction_hash:sha(id('transaction')),audience:'test-fixed-agent',redirect_uri:'https://coze.nankai.edu.cn/product/llm/info/oauth',state:'fictional-fixed-state',scopes:scope};
 assert.equal((await oauth('authorize_start',request)).ok,true);
 const code=sha(id('oauth-code'));
 assert.equal((await oauth('authorize_approve',{session_hash:login.token_hash,transaction_hash:request.transaction_hash,decision:'allow',code_hash:code})).ok,true);
 const token=sha(id('grant'));
 const exchanged=await oauth('exchange',{code_hash:code,audience:request.audience,redirect_uri:request.redirect_uri,token_hash:token});
 assert.equal(exchanged.ok,true);assert.deepEqual(exchanged.data.scopes,scope.split(' '));
 const start={challenge_hash:sha(id('secret')),code_hash:sha(id('display'))};
 assert.equal((await device('start',start)).ok,true);
 const bind={grant_hash:token,audience:request.audience,code_hash:start.code_hash,confirm_binding:true};
 const claim={challenge_hash:start.challenge_hash,token_hash:sha(id('child')),csrf_hash:sha(id('csrf'))};
 return {login,start,bind,claim};
}
test('display code is stable, no table data available to public/service roles, no anonymous RPC',async()=>{
 for(const role of ['anon','authenticated','service_role']){
  assert.equal((await pg.query("SELECT has_table_privilege($1,'nku_identity_pilot_v1.agent_devices','SELECT') ok",[role])).rows[0].ok,false);
  assert.equal((await pg.query("SELECT has_function_privilege($1,'public.nku_competition_oauth_v1_before_devices_rpc(text,jsonb)','EXECUTE') ok",[role])).rows[0].ok,false);
 }
 const a=await setup();assert.equal((await device('start',a.start)).ok,true);
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"authenticated\"}',false)");
 assert.equal((await device('probe')).code,'FORBIDDEN');
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"service_role\"}',false)");
});
test('old scopes cannot bind and are not upgraded by enabling new migration',async()=>{
 const a=await setup('demo:read tasks:read tasks:write');
 assert.equal((await device('bind',a.bind)).code,'FORBIDDEN');
 const row=(await pg.query('SELECT scopes FROM nku_competition_oauth_v1.grants WHERE token_hash=$1',[a.bind.grant_hash])).rows[0];
 assert.deepEqual(row.scopes,['demo:read','tasks:read','tasks:write']);
});
test('device expiry cannot exceed grant, grant shortening expires child and revoke deletes child only',async()=>{
 const a=await setup();assert.equal((await device('bind',a.bind)).ok,true);
 const bound=await device('claim',a.claim);assert.equal(bound.ok,true);
 assert.equal(bound.data.expires_epoch,253370736000);
 await pg.query('UPDATE nku_competition_oauth_v1.grants SET expires_at=0 WHERE token_hash=$1',[a.bind.grant_hash]);
 assert.equal((await identity('get_workspace',{session_hash:a.claim.token_hash})).code,'AUTH_REQUIRED');
 assert.equal((await pg.query('SELECT expires_at FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=$1',[a.claim.token_hash])).rows[0].expires_at,0);
 assert.equal((await oauth('revoke',{token_hash:a.bind.grant_hash,audience:a.bind.audience})).ok,true);
 assert.equal((await pg.query('SELECT count(*) n FROM nku_identity_pilot_v1.browser_sessions WHERE token_hash=$1',[a.claim.token_hash])).rows[0].n,0);
 assert.equal((await identity('get_workspace',{session_hash:a.login.token_hash})).ok,true);
 assert.equal((await device('start',a.start)).ok,true);
 assert.equal((await device('claim',{...a.claim,token_hash:sha(id('new'))})).data.status,'pending');
});
test('source logout cascades and whitelist removal blocks both Agent and device access',async()=>{
 const a=await setup();await device('bind',a.bind);await device('claim',a.claim);
 assert.equal((await identity('logout',{session_hash:a.login.token_hash,csrf_hash:a.login.csrf_hash})).ok,true);
 assert.equal((await identity('get_workspace',{session_hash:a.claim.token_hash})).code,'AUTH_REQUIRED');
 const b=await setup();await device('bind',b.bind);await device('claim',b.claim);
 await pg.query('DELETE FROM nku_identity_pilot_v1.approved_subjects WHERE subject_id=$1',[owners[0]]);
 assert.ok(['AUTH_REQUIRED','FORBIDDEN'].includes((await identity('get_workspace',{session_hash:b.claim.token_hash})).code));
 assert.ok(['AUTH_REQUIRED','FORBIDDEN'].includes((await device('bind',b.bind)).code));
 assert.equal((await identity('configure_subjects',{subjects:owners})).ok,true);
});
test('identity overrides, false confirmation, display-code theft and active grant replacement rejected',async()=>{
 const a=await setup();
 for(const key of ['owner_subject_id','workspace_ref','SYS_USERID'])
  assert.equal((await device('bind',{...a.bind,[key]:'injected'})).code,'VALIDATION_ERROR');
 assert.equal((await device('bind',{...a.bind,confirm_binding:false})).code,'CONFIRMATION_REQUIRED');
 assert.equal((await device('claim',{...a.claim,challenge_hash:a.start.code_hash})).code,'AUTH_REQUIRED');
 await device('bind',a.bind);await device('claim',a.claim);
 const b=await setup();
 assert.equal((await device('bind',{...b.bind,code_hash:a.start.code_hash})).code,'STALE_REVISION');
});
