// Actual isolated PostgreSQL. No cloud credentials or production modifications.
import test, {before, after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
const sha=x=>createHash('sha256').update(x).digest('hex');
let pg,a,b,workspace,task;
const call=async(name,op,args={})=>(await pg.query(`SELECT public.${name}($1,$2::jsonb) r`,[op,JSON.stringify(args)])).rows[0].r;
const old=(op,args)=>call('nku_identity_pilot_v1_rpc',op,args);
const rpc=(op,args)=>call('nku_task_calendar_v1_rpc',op,args);
before(async()=>{
  pg=new PGlite(); await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  for(const name of ['schema.sql','competition-oauth-migration.sql','notice-text-migration.sql','task-calendar-migration.sql'])
    await pg.exec(await readFile(new URL('../'+name,import.meta.url),'utf8'));
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  const subjects=['a','b'].map(x=>'cloudbase_pilot_'+sha('fictional-calendar-'+x));
  assert.equal((await old('configure_subjects',{subjects})).ok,true);
  const owners=[];
  for(const [i,subject_id] of subjects.entries()){
    const auth={subject_id,token_hash:sha('calendar-session-'+i),csrf_hash:sha('calendar-csrf-'+i),workspace_ref:'pilot_workspace_'+String(i).repeat(24)};
    const logged=await old('login',auth); assert.equal(logged.ok,true);
    owners.push({principal_kind:'browser',session_hash:auth.token_hash,csrf_hash:auth.csrf_hash});
    if(i===0)workspace=logged.data.workspace_ref;
  }
  [a,b]=owners;
  const notice=JSON.parse(await readFile(new URL('../../../fixtures/notice-event.demo.json',import.meta.url),'utf8'));
  const hash=sha(JSON.stringify(notice));
  await pg.query('INSERT INTO nku_identity_pilot_v1.fixtures VALUES($1,$2,$3::jsonb)',[hash,'task',JSON.stringify(notice)]);
  const auth={session_hash:a.session_hash,csrf_hash:a.csrf_hash};
  assert.equal((await old('create_draft',{...auth,kind:'task',payload_hash:hash,draft_id:'calendar-sql-draft',key:'calendar-sql-create',request_hash:sha('create')})).ok,true);
  assert.equal((await old('confirm',{...auth,draft_id:'calendar-sql-draft',revision:1,payload_hash:hash,confirmation_id:'calendar-sql-confirm',confirmation_hash:sha('confirm'),key:'calendar-sql-confirm',request_hash:sha('confirm')})).ok,true);
  assert.equal((await old('commit',{...auth,kind:'task',confirmation_hash:sha('confirm'),resource_id:'calendar-sql-task',key:'calendar-sql-commit',request_hash:sha('commit')})).ok,true);
  task=(await rpc('records',a)).data.tasks[0];
});
after(async()=>pg?.close());
const state=()=>({workspace_ref:workspace,expected_revision:task.calendar_state.calendar_revision,...Object.fromEntries(['status','scheduled_start','scheduled_end','reminder_minutes'].map(k=>[k,task.calendar_state[k]]))});
async function args(key,changes={}){return {...a,task_id:task.task_id,key,request_hash:sha(key),records_revision:(await rpc('records',a)).data.records_revision,state:{...state(),...changes}};}
test('calendar has two RLS tables and only service-role RPC; helpers private',async()=>{
  const rows=(await pg.query("SELECT relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='nku_task_calendar_v1' AND c.relkind='r'")).rows;
  assert.equal(rows.length,2); assert.ok(rows.every(r=>r.relrowsecurity));
  for(const role of ['anon','authenticated']){
    await pg.exec('SET ROLE '+role);
    await assert.rejects(rpc('probe'),/permission denied/);
    await assert.rejects(pg.query('SELECT * FROM nku_task_calendar_v1.states'),/permission denied/);
    await assert.rejects(pg.query('SELECT nku_task_calendar_v1.rows($1)',[workspace]),/permission denied/);
    await pg.exec('RESET ROLE');
  }
  await pg.query("SELECT set_config('request.jwt.claims','{}',false)");
  assert.equal((await rpc('probe')).status,403);
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
});
test('ownership, CSRF, agent writes and arbitrary owner overrides rejected',async()=>{
  assert.deepEqual((await rpc('records',b)).data.tasks,[]);
  assert.equal((await rpc('records',{...a,owner:'other'})).status,422);
  assert.equal((await rpc('update',{...await args('sql-owner-negative'),...b})).status,404);
  assert.equal((await rpc('update',{...await args('sql-csrf-negative'),csrf_hash:sha('wrong')})).status,403);
  assert.equal((await rpc('lookup',{principal_kind:'agent',grant_mode:'strict',grant_hash:sha('fake'),audience:'fictional',task_id:task.task_id,key:'sql-agent-negative',request_hash:sha('fake')})).status,403);
});
test('strict state types fail without a persisted revision',async()=>{
  for(const change of [{status:null},{scheduled_start:1},{scheduled_start:'2026-09-21T09:20:00'},{reminder_minutes:false},{reminder_minutes:10},{expected_revision:true}])
    assert.equal((await rpc('update',await args('sql-bad-state-'+sha(JSON.stringify(change)).slice(0,8),change))).status,422);
  assert.equal((await rpc('records',a)).data.tasks[0].calendar_state.calendar_revision,0);
});
test('CAS, replay, immutable notice and snapshot transaction race',async()=>{
  const first=await args('sql-calendar-complete',{status:'completed',reminder_minutes:0});
  const stale=await args('sql-calendar-stale',{status:'cancelled'});
  const made=await rpc('update',first);assert.equal(made.ok,true);
  assert.equal(made.data.calendar_revision,1);assert.deepEqual(made.data.notice,task.notice);
  assert.deepEqual(await rpc('update',first),made);
  assert.equal((await rpc('update',{...first,request_hash:sha('changed')})).status,409);
  assert.equal((await rpc('update',stale)).status,409);
  task=(await rpc('records',a)).data.tasks[0];
  assert.equal(task.calendar_state.status,'completed');
  assert.equal((await rpc('update',await args('sql-calendar-old-cas',{expected_revision:0}))).status,409);
  assert.equal((await rpc('update',await args('sql-calendar-fixed-change',{scheduled_start:null,scheduled_end:null,reminder_minutes:null}))).status,422);
});
test('expired workspace prevents cached write replay into a fresh owner workspace',async()=>{
  const cached=await args('sql-workspace-expiry',{status:'cancelled'});
  assert.equal((await rpc('update',cached)).ok,true);
  await pg.query('UPDATE nku_identity_pilot_v1.workspaces SET expires_at=0 WHERE workspace_ref=$1',[workspace]);
  const expired=await rpc('update',cached); assert.equal(expired.ok,false);
  assert.ok([401,403,404].includes(expired.status));
});
