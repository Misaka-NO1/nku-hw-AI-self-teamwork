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
  const invalid=guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}).result;
  assert.equal(invalid.ok,false); assert.equal(invalid.error_code,'FABRICATED_EVIDENCE');
  assert.equal(invalid.saved,false); assert.equal(invalid.status,'invalid_extraction');
  const source=adapter.handler({notice_input:JSON.stringify({...input(),source_text:text+'还有另一事项。'})});
  assert.equal(guard.handler({source_json:source.source_json,extraction:JSON.stringify(model())}).result.ok,false);
});

const missingYearCase=(quote, overrides={})=>{
  const m=model(), n=m.items[0].notice;
  m.items[0].kind='deadline_feasibility'; n.title='完成雨课堂作业';
  n.event={start:null,end:null,date:null,precision:'unknown'};
  n.due={at:null,date:null,precision:'datetime'};
  n.source_spans=['title','due'].map(field=>({field,quote,source_ref:'user-pasted-notice'}));
  return guard.handler({source_json:JSON.stringify({source_text:quote,source_ref:'user-pasted-notice',
    reference_at:null,extracted_at:'2026-10-06T15:00:00Z',...overrides}),extraction:JSON.stringify(m)}).result;
};
test('ordinary month-day deadline defaults to current year instead of crashing',()=>{
  for(const quote of ['邵老师布置了作业，截止时间是 10-09 21:40:00。','交报告，截止10月9日21:40。']) {
    const r=missingYearCase(quote);
    assert.equal(r.ok,true); assert.equal(r.items[0].notice.due.at,'2026-10-09T21:40:00+08:00');
    assert.equal(r.time_assumptions[0].assumption,'omitted_year');
    assert.equal(r.time_assumptions[0].year,2026); assert.equal(r.saved,false);
    assert.equal(r.scheduling_clarifications[0].fields.includes('due_time'),false);
  }
});
test('past month-day stays in this year and is labelled past, never rolls to next year',()=>{
  const r=missingYearCase('交报告，截止09-24 21:40。');
  assert.equal(r.items[0].notice.due.at,'2026-09-24T21:40:00+08:00');
  assert.equal(r.time_assumptions[0].is_past,true);
});
test('reference override and Shanghai year boundary are deterministic',()=>{
  const reference=missingYearCase('交报告，截止10-09 21:40。',{reference_at:'2025-10-06T23:00:00+08:00'});
  assert.equal(reference.items[0].notice.due.at,'2025-10-09T21:40:00+08:00');
  assert.equal(reference.time_assumptions[0].basis,'provided_reference');
  const newYear=missingYearCase('交报告，截止01-02 09:00。',{extracted_at:'2026-12-31T16:30:00Z'});
  assert.equal(newYear.items[0].notice.due.at,'2027-01-02T09:00:00+08:00');
});
test('bad calendar dates, contradictory deadlines and explicit years are not guessed',()=>{
  for(const quote of ['截止02-30 21:40。','截止10-09 21:40，另写10-10 21:40。','截止2025年10月9日21:40。']) {
    const r=missingYearCase(quote); assert.equal(r.ok,false); assert.equal(r.status,'invalid_extraction');
    assert.equal(r.items.length,0); assert.equal(r.saved,false); assert.equal(r.time_check_performed,false);
  }
});
test('malformed model JSON returns an explicit failure rather than throwing through the Agent',()=>{
  const r=guard.handler({source_json:prepared().source_json,extraction:'{not json'});
  assert.equal(r.result.ok,false); assert.equal(r.result.error_code,'INVALID_EXTRACTION');
  assert.equal(r.query_json,''); assert.equal(r.result.can_save,false);
});
test('follow-up whitelist does not turn model speculation into requirements',()=>{
  const m=model(); m.items[0].notice.needs_confirmation.push('registration_method','bring_id','return_trip');
  const r=guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}).result;
  assert.deepEqual(JSON.parse(JSON.stringify(r.scheduling_clarifications)),[]);
  m.items[0].notice.event={start:null,end:null,date:'2026-09-24',precision:'date_only'};
  const missing=guard.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}).result;
  assert.deepEqual(JSON.parse(JSON.stringify(missing.scheduling_clarifications[0].fields)),['event_interval']);
});
