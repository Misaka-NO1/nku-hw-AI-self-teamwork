// Real local PG transactions; no cloud connection or account credentials.
import test, {before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
const sha=value=>createHash('sha256').update(value).digest('hex');
let pg,a,b;
const old=async(op,args)=> (await pg.query('SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) r',[op,JSON.stringify(args)])).rows[0].r;
const rpc=async(op,args={})=> (await pg.query('SELECT public.nku_notice_text_v1_rpc($1,$2::jsonb) r',[op,JSON.stringify(args)])).rows[0].r;
before(async()=>{
  pg=new PGlite(); await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  for(const name of ['schema.sql','competition-oauth-migration.sql','notice-text-migration.sql'])
    await pg.exec(await readFile(new URL('../'+name,import.meta.url),'utf8'));
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  const subjects=['a','b'].map(n=>'cloudbase_pilot_'+sha('fictional-notice-'+n));
  assert.equal((await old('configure_subjects',{subjects})).ok,true);
  const owners=[];
  for(const [i,subject] of subjects.entries()) {
    const auth={subject_id:subject,token_hash:sha('fictional-session-'+i),csrf_hash:sha('fictional-csrf-'+i),
      workspace_ref:'pilot_workspace_'+String(i).repeat(24)};
    assert.equal((await old('login',auth)).ok,true);
    owners.push({principal_kind:'browser',session_hash:auth.token_hash,csrf_hash:auth.csrf_hash});
  }
  [a,b]=owners;
});
after(async()=>pg.close());
const proposal=id=>({plan_version:'notice-text-pilot-v1',kind:'deadline_feasibility',fictional_data_confirmed:true,
  user_confirmations:{source_review:true},notice:{notice_id:id,needs_confirmation:[]},selected_slot:null});
const createArgs=async(id,owner=a)=>({ ...owner,plan:proposal(id),payload_hash:sha(id),
  records_revision:(await rpc('records',owner)).data.records_revision,draft_id:id,key:id+'-create',request_hash:sha(id+'-create')});
test('only four new RLS tables; old fifteen remain; private RPC is server-only',async()=>{
  const rows=await pg.query("SELECT n.nspname,c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname IN ('nku_identity_pilot_v1','nku_notice_text_v1')");
  assert.equal(rows.rows.filter(r=>r.nspname==='nku_identity_pilot_v1').length,15);
  assert.equal(rows.rows.filter(r=>r.nspname==='nku_notice_text_v1').length,4);
  assert.ok(rows.rows.every(r=>r.relrowsecurity));
  const perms=await pg.query("SELECT has_function_privilege('anon','public.nku_notice_text_v1_rpc(text,jsonb)','EXECUTE') a,has_function_privilege('authenticated','public.nku_notice_text_v1_rpc(text,jsonb)','EXECUTE') b");
  assert.equal(perms.rows[0].a,false);assert.equal(perms.rows[0].b,false);
});
test('role, owner overrides, ambiguous mode and agent writes are refused',async()=>{
  await pg.query("SELECT set_config('request.jwt.claims','{}',false)");
  assert.equal((await rpc('probe')).status,403);
  await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
  assert.equal((await rpc('records',{...a,owner:'foreign'})).status,422);
  assert.equal((await rpc('records',{...a,workspace_ref:'foreign'})).status,422);
  assert.equal((await rpc('records',{...a,grant_hash:sha('fake')})).status,422);
  assert.equal((await rpc('commit',{principal_kind:'agent',grant_mode:'strict',grant_hash:sha('fake'),audience:'fictional-agent',
    confirmation_hash:sha('c'),resource_id:'fake',records_revision:'x',key:'fake-key-1',request_hash:sha('r')})).status,403);
});
test('idempotent create and foreign draft read protection',async()=>{
  const args=await createArgs('notice-sql-draft-1');
  const made=await rpc('create',args);assert.equal(made.ok,true);
  assert.deepEqual(await rpc('create',args),made);
  assert.equal((await rpc('get_draft',{...b,draft_id:args.draft_id})).status,404);
  assert.equal((await rpc('create',{...args,request_hash:sha('changed-body')})).status,409);
});
test('draft changes invalidate old receipt and repeated update is stable',async()=>{
  const created=await rpc('create',await createArgs('notice-sql-draft-2'));
  const d=created.data, revision=(await rpc('records',a)).data.records_revision;
  const c={...a,draft_id:d.draft_id,revision:d.revision,payload_hash:d.payload_hash,
    confirmation_id:'sql-confirm-2',confirmation_hash:sha('sql-confirm-2'),records_revision:revision,key:'sql-confirm-2',request_hash:sha('sql-confirm-2')};
  assert.equal((await rpc('confirm',c)).ok,true);
  const update={...a,draft_id:d.draft_id,revision:1,plan:proposal('changed-notice'),payload_hash:sha('changed-notice'),
    records_revision:revision,key:'sql-update-2',request_hash:sha('sql-update-2')};
  const updated=await rpc('update',update);assert.equal(updated.data.revision,2);
  assert.deepEqual(await rpc('update',update),updated);
  assert.equal((await rpc('get_confirmation',{...a,confirmation_hash:c.confirmation_hash})).status,409);
});
test('snapshot change rejects a stale write inside the transaction',async()=>{
  const snapshot=(await rpc('records',a)).data.records_revision;
  const plan=await createArgs('notice-sql-draft-3');const d=(await rpc('create',plan)).data;
  const c={...a,draft_id:d.draft_id,revision:1,payload_hash:d.payload_hash,
    confirmation_id:'sql-confirm-3',confirmation_hash:sha('sql-confirm-3'),records_revision:snapshot,key:'sql-confirm-3',request_hash:sha('sql-confirm-3')};
  assert.equal((await rpc('confirm',c)).ok,true);
  const commit={...a,confirmation_hash:c.confirmation_hash,records_revision:snapshot,resource_id:'notice-sql-task-3',key:'sql-commit-3',request_hash:sha('sql-commit-3')};
  const saved=await rpc('commit',commit);assert.equal(saved.ok,true);assert.deepEqual(await rpc('commit',commit),saved);
  const another={...await createArgs('notice-sql-draft-4'),records_revision:snapshot};
  assert.equal((await rpc('create',another)).status,409);
  assert.equal((await rpc('get_task',{...b,task_id:'notice-sql-task-3'})).status,404);
});
test('expired underlying identity cannot read or replay a save',async()=>{
  await pg.query('UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0 WHERE token_hash=$1',[a.session_hash]);
  assert.equal((await rpc('records',a)).status,401);
});
