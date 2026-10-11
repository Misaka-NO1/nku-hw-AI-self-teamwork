// Local real PostgreSQL only. No network, credentials, or real student records.
import assert from 'node:assert/strict';
import { before, after, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
const sha=s=>createHash('sha256').update(s).digest('hex');
const id=p=>p+randomBytes(18).toString('base64url');
let pg,a,b;
const call=async(fn,op,args={})=>(await pg.query(`SELECT public.${fn}($1,$2::jsonb) result`,[op,JSON.stringify(args)])).rows[0].result;
const rpc=(op,args={})=>call('nku_personal_degree_v1_rpc',op,args);
const pilot=(op,args={})=>call('nku_identity_pilot_v1_rpc',op,args);
const competition=(op,args={})=>call('nku_competition_oauth_v1_rpc',op,args);
function observation(){return {kind:'degree-table-observation',source:{url:'https://eamis.nankai.edu.cn/eams/myPlanCompl.action',captured_at:'2026-10-10T00:00:00Z',coverage:'partial',adapter_verified:false},
 headers:['序号','课程序号','课程名称','要求学分','实修学分','成绩','是否通过','备注'],rows:[
 {locator:'table-row:2',cells:['1 虚构专业必修模块（所有子项满足）','4','2','','缺2学分','']},
 {locator:'table-row:3',cells:['1','ANON-01','虚构在读课程','2','2','--','是','在读，必修']}]};}
function draftArgs(){const o=observation(),r={source:o.source,modules:[{locator:'table-row:2'}],courses:[{state:'in_progress'}],can_decide_complete:false};
 return {observation:o,report:r,payload_hash:sha(JSON.stringify({o,r})),report_hash:sha(JSON.stringify(r)),draft_id:id('draft_'),key:id('draft-key-'),request_hash:sha(JSON.stringify(o))};}
async function login(subject){const token=sha(id('session')),csrf=sha(id('csrf'));const out=await pilot('login',{subject_id:subject,token_hash:token,csrf_hash:csrf,workspace_ref:id('pilot_workspace_')});
 assert.equal(out.ok,true);return {principal_kind:'browser',session_hash:token,csrf_hash:csrf};}
async function make(owner){const args={...owner,...draftArgs()},out=await rpc('draft',args);assert.equal(out.ok,true,JSON.stringify(out));return {args,result:out.data,...out.data};}
function confirmation(owner,d){const raw=id('confirmation_');return {...owner,draft_id:d.draft_id,revision:d.revision,payload_hash:d.payload_hash,report_hash:d.report_hash,
 share_with_agent:true,confirmation_id:raw,confirmation_hash:sha(raw),key:id('confirm-key-'),request_hash:sha(raw)};}
async function confirm(owner,d){const args=confirmation(owner,d),out=await rpc('confirm',args);assert.equal(out.ok,true,JSON.stringify(out));return {args,...out.data};}
function commitArgs(owner,c){return {...owner,confirmation_hash:c.args.confirmation_hash,share_with_agent:true,resource_id:id('degree_'),key:id('commit-key-'),request_hash:sha(c.confirmation_id)};}
async function save(owner){const d=await make(owner),c=await confirm(owner,d),args=commitArgs(owner,c),out=await rpc('commit',args);assert.equal(out.ok,true,JSON.stringify(out));return {d,c,args,out};}
async function grant(owner,mode='competition'){
 const audience='test-school-agent',redirect_uri='https://coze.nankai.edu.cn/product/llm/info/oauth',transaction_hash=sha(id('tx')),code_hash=sha(id('code')),token_hash=sha(id('grant'));
 const challenge='E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM';
 const start={session_hash:owner.session_hash,transaction_hash,audience,redirect_uri,state:'degree-test-state'};
 const approve={session_hash:owner.session_hash,transaction_hash,code_hash,decision:'allow'};
 if(mode==='competition'){
  assert.equal((await competition('authorize_start',start)).ok,true);
  assert.equal((await competition('authorize_approve',approve)).ok,true);
  assert.equal((await competition('exchange',{code_hash,audience,redirect_uri,token_hash})).ok,true);
 }else{
  assert.equal((await pilot('authorize_start',{...start,scopes:['demo:read'],challenge})).ok,true);
  assert.equal((await pilot('authorize_approve',approve)).ok,true);
  assert.equal((await pilot('oauth_exchange',{code_hash,audience,redirect_uri,token_hash,challenge})).ok,true);
 }
 return {principal_kind:'agent',grant_mode:mode,grant_hash:token_hash,audience};
}
before(async()=>{
 pg=new PGlite();await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
 for(const file of ['schema.sql','competition-oauth-migration.sql','personal-degree-migration.sql'])await pg.exec(await readFile(new URL('../'+file,import.meta.url),'utf8'));
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"service_role\"}',false)");
 const subjects=['cloudbase_pilot_'+sha('degree-a'),'cloudbase_pilot_'+sha('degree-b')];
 assert.equal((await pilot('configure_subjects',{subjects})).ok,true);a=await login(subjects[0]);b=await login(subjects[1]);
});
after(async()=>pg?.close());
test('separate RLS tables, no existing function replacement or direct client access',async()=>{
 assert.equal((await rpc('probe',{})).data.schema_version,'personal-degree-v1');
 for(const role of ['anon','authenticated','service_role'])for(const table of ['degree_drafts','degree_confirmations','degree_snapshots','degree_idempotency']){
  const row=(await pg.query("SELECT has_table_privilege($1,$2,'SELECT') allowed",[role,'nku_personal_degree_v1.'+table])).rows[0];assert.equal(row.allowed,false);
 }
 const sql=await readFile(new URL('../personal-degree-migration.sql',import.meta.url),'utf8');
 assert.doesNotMatch(sql,/ALTER FUNCTION|CREATE OR REPLACE FUNCTION public\.nku_(?:identity|competition)/);
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"anon\"}',false)");assert.equal((await rpc('probe',{})).code,'FORBIDDEN');
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"service_role\"}',false)");
});
test('drafts invisible until explicit confirmation; owner and CSRF isolation',async()=>{
 assert.equal((await rpc('current',a)).data,null);assert.equal((await rpc('records',await grant(a))).data,null);
 const d=await make(a);assert.equal((await rpc('current',a)).data,null);
 assert.equal((await rpc('get_draft',{...b,draft_id:d.draft_id})).code,'NOT_FOUND');
 const fetched=await rpc('get_draft',{...a,draft_id:d.draft_id});assert.equal(fetched.data.kind,'degree');assert.deepEqual(fetched.data.payload,d.args.observation);
 assert.equal((await rpc('confirm',{...confirmation(a,d),share_with_agent:false})).code,'FORBIDDEN');
 assert.equal((await rpc('draft',{...d.args,csrf_hash:sha('wrong'),key:id('wrong-key-')})).code,'FORBIDDEN');
 assert.equal((await rpc('current',{...a,workspace_ref:'another'})).code,'VALIDATION_ERROR');
});
test('commit replay safe even after expiry; version readback and cross-owner refusal',async()=>{
 const d=await make(a),c=await confirm(a,d),args=commitArgs(a,c);
 assert.equal((await rpc('commit',{...args,...b})).code,'NOT_FOUND');
 const result=await rpc('commit',args);assert.equal(result.ok,true);assert.equal(result.data.revision,1);
 assert.deepEqual(await rpc('commit',args),result);
 await pg.query('UPDATE nku_personal_degree_v1.degree_confirmations SET expires_at=0 WHERE confirmation_hash=$1',[c.args.confirmation_hash]);
 assert.deepEqual(await rpc('commit',args),result);
 assert.equal((await rpc('commit',{...args,request_hash:sha('changed')})).code,'STALE_REVISION');
 const current=await rpc('current',a);assert.deepEqual(current.data.observation,d.args.observation);assert.deepEqual(current.data.report,d.args.report);
 assert.equal((await rpc('current',b)).data,null);
});
test('stale drafts cannot overwrite newer snapshots, even with a prior receipt',async()=>{
 const stale=await make(a),receipt=await confirm(a,stale);await save(a);
 assert.equal((await rpc('commit',commitArgs(a,receipt))).code,'STALE_REVISION');
 assert.equal((await rpc('confirm',confirmation(a,stale))).code,'STALE_REVISION');
});
test('strict and compatibility Agent read own saved data; no writes, owner override or revoked grant',async()=>{
 for(const mode of ['strict','competition']){
  const auth=await grant(a,mode),read=await rpc('records',auth);assert.equal(read.ok,true);assert.notEqual(read.data,null);assert.deepEqual(read.data.report,(await rpc('current',a)).data.report);
  const other=await grant(b,mode);assert.equal((await rpc('records',other)).data,null);
  assert.equal((await rpc('records',{...auth,workspace_ref:'other'})).code,'VALIDATION_ERROR');
  assert.equal((await rpc('draft',{...auth,...draftArgs()})).code,'FORBIDDEN');
  if(mode==='competition')await competition('revoke',{token_hash:auth.grant_hash,audience:auth.audience});
  else await pilot('oauth_revoke',{token_hash:auth.grant_hash,audience:auth.audience});
  assert.equal((await rpc('records',auth)).ok,false);
 }
});
test('invalid sources, identity text, unknown keys and fake verified adapter rejected',async()=>{
 for(const change of [o=>{o.source.url='https://other.invalid';},o=>{o.source.adapter_verified=true;},o=>{o.rows[0].cells[0]='姓名：private-test';},o=>{o.extra='unexpected';},o=>{o.rows=[];}]){
  const args=draftArgs();change(args.observation);assert.equal((await rpc('draft',{...a,...args})).code,'VALIDATION_ERROR');
 }
 const args=draftArgs();args.report.source={...args.report.source,captured_at:'2000-01-01T00:00:00Z'};
 assert.equal((await rpc('draft',{...a,...args})).code,'VALIDATION_ERROR');
});
test('expired drafts and receipts fail; draft replay stays safe after commit',async()=>{
 const d=await make(b),c=await confirm(b,d);
 await pg.query('UPDATE nku_personal_degree_v1.degree_confirmations SET expires_at=0 WHERE confirmation_hash=$1',[c.args.confirmation_hash]);
 assert.equal((await rpc('commit',commitArgs(b,c))).code,'TOKEN_EXPIRED');
 await pg.query('UPDATE nku_personal_degree_v1.degree_drafts SET expires_at=0 WHERE draft_id=$1',[d.draft_id]);
 assert.equal((await rpc('get_draft',{...b,draft_id:d.draft_id})).code,'TOKEN_EXPIRED');
 const saved=await save(b);assert.deepEqual((await rpc('draft',saved.d.args)).data,saved.d.result);
 assert.equal((await rpc('current',b)).data.revision,1);
});
test('logout revokes Agent and browser access; other owner unchanged',async()=>{
 const auth=await grant(b),before=(await rpc('current',a)).data;
 assert.equal((await pilot('logout',{session_hash:b.session_hash,csrf_hash:b.csrf_hash})).ok,true);
 assert.equal((await rpc('current',b)).code,'AUTH_REQUIRED');assert.equal((await rpc('records',auth)).ok,false);
 assert.deepEqual((await rpc('current',a)).data,before);
});
