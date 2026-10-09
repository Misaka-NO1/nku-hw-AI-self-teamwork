import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
const sha=s=>createHash('sha256').update(s).digest('hex');
const id=p=>p+randomBytes(18).toString('base64url');
let pg,a,b;
const rpc=async(op,args={})=>(await pg.query('SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) result',[op,JSON.stringify(args)])).rows[0].result;
async function login(owner){const args={subject_id:owner,token_hash:sha(id('session')),csrf_hash:sha(id('csrf')),workspace_ref:id('pilot_workspace_')};const r=await rpc('login',args);assert.equal(r.ok,true);return {session_hash:args.token_hash,csrf_hash:args.csrf_hash,workspace_ref:r.data.workspace_ref};}
async function draft(owner,tag='one'){const payload={schema_version:'1.0.0',dataset_kind:'personal',courses:[{title:tag}]};const args={...owner,kind:'schedule',payload,payload_hash:sha(JSON.stringify(payload)),draft_id:id('draft_'),key:id('draft-key-'),request_hash:sha(tag+id('req'))};const r=await rpc('create_draft',args);assert.equal(r.ok,true);return {args,...r.data};}
async function confirm(owner,d){const raw=id('confirmation_');const args={...owner,draft_id:d.draft_id,revision:1,payload_hash:d.payload_hash,confirmation_id:raw,confirmation_hash:sha(raw),key:id('confirm-key-'),request_hash:sha(raw)};const r=await rpc('confirm',args);assert.equal(r.ok,true);return {args,...r.data};}
const commitArgs=(owner,c)=>({...owner,kind:'schedule',confirmation_hash:c.args.confirmation_hash,resource_id:id('schedule_'),key:id('commit-key-'),request_hash:sha(c.confirmation_id)});
before(async()=>{pg=new PGlite();await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');await pg.exec(await readFile(new URL('../schema.sql',import.meta.url),'utf8'));await pg.exec(await readFile(new URL('../personal-schedules-migration.sql',import.meta.url),'utf8'));await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"service_role\"}',false)");const owners=['cloudbase_pilot_'+sha('a'),'cloudbase_pilot_'+sha('b')];assert.equal((await rpc('configure_subjects',{subjects:owners})).ok,true);a=await login(owners[0]);b=await login(owners[1]);});
after(async()=>{await pg.close();});
test('personal payload persists, requires explicit confirmation and reads back isolated',async()=>{
 const d=await draft(a,'first personal course');
 assert.equal((await rpc('current_schedule',a)).code,'NOT_FOUND');
 assert.equal((await rpc('get_draft',{...b,draft_id:d.draft_id})).code,'NOT_FOUND');
 const c=await confirm(a,d),args=commitArgs(a,c);
 assert.equal((await rpc('commit',{...args,...b})).code,'NOT_FOUND');
 const saved=await rpc('commit',args);assert.equal(saved.ok,true);assert.equal(saved.data.revision,1);
 assert.deepEqual(await rpc('commit',args),saved);
 const current=await rpc('current_schedule',a);assert.deepEqual(current.data.timetable,d.args.payload);
 assert.equal((await rpc('current_schedule',{...b,workspace_ref:a.workspace_ref})).code,'NOT_FOUND');
 assert.equal((await rpc('records',a)).data.schedule.revision,1);
 assert.equal((await rpc('current_schedule',b)).code,'NOT_FOUND');
});
test('old draft cannot overwrite a newer saved revision, even with a prior receipt',async()=>{
 const stale=await draft(a,'stale'),staleC=await confirm(a,stale);
 const latest=await draft(a,'latest'),c=await confirm(a,latest);
 assert.equal((await rpc('commit',commitArgs(a,c))).ok,true);
 assert.equal((await rpc('commit',commitArgs(a,staleC))).code,'STALE_REVISION');
 assert.equal((await rpc('confirm',{...staleC.args,key:id('retry-confirm-')})).code,'STALE_REVISION');
 assert.equal((await rpc('current_schedule',a)).data.timetable.courses[0].title,'latest');
});
test('CSRF, principal restrictions and same-key changed body are enforced',async()=>{
 const d=await draft(b,'owner B');
 assert.equal((await rpc('create_draft',{...d.args,csrf_hash:sha('wrong'),key:id('wrong-csrf-')})).code,'FORBIDDEN');
 assert.equal((await rpc('create_draft',{...d.args,principal_kind:'agent'})).code,'FORBIDDEN');
 assert.equal((await rpc('create_draft',{...d.args,request_hash:sha('different')})).code,'STALE_REVISION');
 assert.deepEqual((await rpc('create_draft',d.args)).data.draft_id,d.draft_id);
});
test('expired drafts and receipts cannot save; logout invalidates access',async()=>{
 const d=await draft(b,'expiry');const c=await confirm(b,d);
 await pg.query('UPDATE nku_identity_pilot_v1.personal_schedule_confirmations SET expires_at=0 WHERE confirmation_hash=$1',[c.args.confirmation_hash]);
 assert.equal((await rpc('commit',commitArgs(b,c))).code,'CONFIRMATION_REQUIRED');
 await pg.query('UPDATE nku_identity_pilot_v1.personal_schedule_drafts SET expires_at=0 WHERE draft_id=$1',[d.draft_id]);
 assert.equal((await rpc('get_draft',{...b,draft_id:d.draft_id})).code,'TOKEN_EXPIRED');
 assert.equal((await rpc('logout',b)).ok,true);
 assert.equal((await rpc('records',b)).code,'AUTH_REQUIRED');
});
test('tables and the pre-migration bypass RPC remain inaccessible to clients',async()=>{
 for(const role of ['anon','authenticated','service_role']) {
  const result=await pg.query("SELECT has_table_privilege($1,'nku_identity_pilot_v1.personal_schedules','SELECT') permitted",[role]);assert.equal(result.rows[0].permitted,false);
 }
 await pg.query("SELECT set_config('request.jwt.claims','{\"role\":\"anon\"}',false)");assert.equal((await rpc('records',a)).code,'FORBIDDEN');
});
