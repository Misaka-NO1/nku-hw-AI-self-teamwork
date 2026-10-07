import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const context={}; vm.runInNewContext(readFileSync(new URL('./notice-schedule-prepare.js',import.meta.url),'utf8'),context);
const at=(d,h)=>`2026-10-${d}T${h}:00+08:00`;
const base=()=>({scenario:'deadline',revision:1,reviewed:true,reference_at:at('06','12:00'),window:{start:at('07','08:00'),end:at('09','18:00')},available_windows:[],buffers:{before_minutes:0,after_minutes:0},alternatives:null,task:{title:'写作业',due_at:at('09','18:00'),estimated_minutes:60,earliest_start:at('07','08:00')}});
const run=p=>JSON.parse(JSON.stringify(context.compilePlan({plan_input:JSON.stringify(p)}).result));
test('DDL is a deadline not a busy event; compiler does not pretend calculation/save',()=>{
 const r=run(base()),q=JSON.parse(r.checks[0].query_json);
 assert.equal(q.kind,'deadline_feasibility');assert.equal(q.event,null);assert.equal(q.due.at,at('09','18:00'));
 assert.equal(r.saved,false);assert.equal(r.time_check_performed,false);
});
test('missing deadline, estimate, earliest time and unreviewed source block queries',()=>{
 const p=base();p.reviewed=false;p.task.due_at=null;p.task.estimated_minutes=null;p.task.earliest_start=null;
 const r=run(p);assert.equal(r.checks.length,0);assert.deepEqual(r.needs_confirmation,['source_review','due_time','estimated_minutes','earliest_start']);
});
test('DDL edit and estimate edit invalidate menu fingerprint',()=>{
 const p=base(),old=run(p).menu_id;p.task.due_at=at('09','17:00');assert.notEqual(run(p).menu_id,old);
 p.task.estimated_minutes=90;assert.notEqual(run(p).menu_id,old);
});
test('evening-only windows produce independent actual tool requests',()=>{
 const p=base();p.available_windows=[{start:at('07','19:00'),end:at('07','21:00')},{start:at('08','19:00'),end:at('08','21:00')}];
 const r=run(p);assert.equal(r.checks.length,2);assert.equal(JSON.parse(r.checks[1].query_json).window.start,at('08','19:00'));
});
const events=()=>({...base(),scenario:'alternatives',task:null,alternatives:[{option_id:'a',title:'活动第一场',start:at('07','09:00'),end:at('07','10:00')},{option_id:'b',title:'活动第二场',start:at('07','14:00'),end:at('07','15:00')}]});
test('alternative sessions are separate event checks, not all scheduled simultaneously',()=>{
 const r=run(events());assert.deepEqual(r.checks.map(c=>c.option_id),['a','b']);
 for(const c of r.checks){const q=JSON.parse(c.query_json);assert.equal(q.kind,'event_conflict');assert.equal(q.due,null);}
});
test('fixed event supports one interval only; unknown end is clarification',()=>{
 const p=events();p.scenario='fixed_event';assert.throws(()=>run(p),/INVALID_ALTERNATIVES/);
 p.alternatives=[p.alternatives[0]];p.alternatives[0].end=null;assert.equal(run(p).checks.length,0);
 assert.equal(run(p).needs_confirmation[0],'a:event_time');
});
test('historical notice is not silently moved to today',()=>{
 const p=events();p.reference_at=at('08','12:00');assert.equal(run(p).checks.length,0);
 const d=base();d.reference_at=at('10','12:00');assert.deepEqual(run(d).needs_confirmation,['past_deadline','earliest_start_before_reference']);
});
test('past earliest start needs a new reviewed boundary; event buffers are not silently ignored',()=>{
 const d=base();d.task.earliest_start=at('05','08:00');assert.equal(run(d).checks.length,0);
 assert.deepEqual(run(d).needs_confirmation,['earliest_start_before_reference']);
 const e=events();e.buffers.before_minutes=15;assert.equal(run(e).checks.length,0);
 assert.deepEqual(run(e).needs_confirmation,['event_buffer_not_supported']);
});
test('invalid dates, duplicate IDs, overlapping preference windows and injected identity are rejected',()=>{
 const p=base();p.task.due_at='2026-02-30T18:00:00+08:00';assert.throws(()=>run(p),/INVALID_TIME/);
 const e=events();e.alternatives[1].option_id='a';assert.throws(()=>run(e),/INVALID_OPTION_ID/);
 const d=base();d.available_windows=[{start:at('07','19:00'),end:at('07','21:00')},{start:at('07','20:00'),end:at('07','22:00')}];assert.throws(()=>run(d),/INVALID_AVAILABLE_WINDOWS/);
 assert.throws(()=>run({...base(),owner:'someone'}),/INVALID_PLAN/);
});
test('school adapter reports invalid input without crashing Agent or emitting requests',()=>{
 const r=context.handler({plan_input:'{broken'}).result;
 assert.equal(r.status,'invalid_input');assert.equal(r.error_code,'INVALID_JSON');
 assert.equal(r.checks.length,0);assert.equal(r.saved,false);assert.equal(r.time_check_performed,false);
 assert.equal(context.handler({plan_input:JSON.stringify({...base(),owner:'x'})}).result.error_code,'INVALID_PLAN');
});
