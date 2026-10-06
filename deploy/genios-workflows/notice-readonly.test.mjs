import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const adapter={}, guard={};
vm.runInNewContext(readFileSync(new URL('./notice-readonly-school-input.js',import.meta.url),'utf8'),adapter);
vm.runInNewContext(readFileSync(new URL('./notice-readonly-validate.js',import.meta.url),'utf8'),guard);
const text='请于2026年9月24日19:00至20:30参加观摩活动。';
const input=()=>({source_text:text,source_ref:'user-pasted-notice',reference_at:null});
const prepared=()=>adapter.handler({notice_input:JSON.stringify(input())});
const model=()=>({items:[{kind:'event_conflict',notice:{schema_version:'1.0.0',notice_id:'item-1',
  title:'参加观摩活动',published_at:null,extracted_at:'2026-09-24T00:00:00+08:00',timezone:'Asia/Shanghai',
  event:{start:'2026-09-24T19:00:00+08:00',end:'2026-09-24T20:30:00+08:00',date:null,precision:'datetime'},
  due:{at:null,date:null,precision:'unknown'},estimated_minutes:null,earliest_start:null,materials:[],
  source_spans:[{field:'title',quote:text,source_ref:'user-pasted-notice'},
    {field:'event',quote:text,source_ref:'user-pasted-notice'}],needs_confirmation:['source_review']}}],unclassified:[]});
test('reader preserves pasted source without pretending it is fictional',()=>{
  const result=prepared(); assert.equal(JSON.parse(result.model_input).source_text,text);
  assert.equal(Object.hasOwn(JSON.parse(result.model_input),'fictional_data_confirmed'),false);
});
test('read-only result cannot emit cloud save transport or claim time calculation',()=>{
  const result=guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(model())});
  assert.equal(result.result.ok,true); assert.equal(result.result.can_save,false);
  assert.equal(result.result.saved,false); assert.equal(result.result.time_check_performed,false);
  assert.equal(result.result.source_scope,'user_provided_read_only'); assert.equal(result.query_json,'');
});
test('identity fields, false fictional labels, oversized source and invalid dates are rejected',()=>{
  for(const extra of [{owner:'other'},{fictional_data_confirmed:true},
    {source_text:'x'.repeat(20001)},{reference_at:'2026-02-30T10:00:00+08:00'}]) {
    assert.throws(()=>adapter.handler({notice_input:JSON.stringify({...input(),...extra})}));
  }
});
test('read-only guard retains evidence and unread source rejection',()=>{
  const m=model(); m.items[0].notice.source_spans[0].quote='模型自己写的通知';
  assert.throws(()=>guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}),/FABRICATED_EVIDENCE/);
  const source=adapter.handler({notice_input:JSON.stringify({...input(),source_text:text+'还有另一事项。'})});
  assert.equal(guard.handler({source_json:source.source_json,extraction:JSON.stringify(model())}).result.ok,false);
});
test('follow-up whitelist does not turn model speculation into requirements',()=>{
  const m=model(); m.items[0].notice.needs_confirmation.push('registration_method','bring_id','return_trip');
  const r=guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}).result;
  assert.deepEqual(JSON.parse(JSON.stringify(r.scheduling_clarifications)),[]);
  m.items[0].notice.event={start:null,end:null,date:'2026-09-24',precision:'date_only'};
  const missing=guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}).result;
  assert.deepEqual(JSON.parse(JSON.stringify(missing.scheduling_clarifications[0].fields)),['event_interval']);
});
