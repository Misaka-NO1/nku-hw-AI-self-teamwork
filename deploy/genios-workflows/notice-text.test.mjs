import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const inputContext = {};
vm.runInNewContext(readFileSync(new URL('./notice-text-input.js', import.meta.url), 'utf8'), inputContext);
const validator = {};
vm.runInNewContext(readFileSync(new URL('./notice-text-validate.js', import.meta.url), 'utf8'), validator);
const schoolInput = {};
vm.runInNewContext(readFileSync(new URL('./notice-school-input.js', import.meta.url), 'utf8'), schoolInput);
const text = '请在2026年9月21日10:10前提交虚构新设计。';
const prepared = () => inputContext.handler({source_text:text,source_ref:'self-authored',reference_at:''});
const model = () => ({items:[{kind:'deadline_feasibility',notice:{schema_version:'1.0.0',notice_id:'item-1',
  title:'提交虚构新设计',published_at:null,extracted_at:'2026-09-21T00:00:00+08:00',timezone:'Asia/Shanghai',
  event:{start:null,end:null,date:null,precision:'unknown'},due:{at:'2026-09-21T10:10:00+08:00',date:null,precision:'datetime'},
  estimated_minutes:null,earliest_start:null,materials:[],source_spans:[{field:'due',quote:text,source_ref:'self-authored'}],
  needs_confirmation:[]}}],unclassified:[]});
test('new text goes unchanged to model, with no fixture id', () => {
  const p=prepared(); assert.equal(JSON.parse(p.model_input).source_text,text);
  assert.equal(Object.hasOwn(JSON.parse(p.model_input),'fixture_id'),false);
});
test('unseen model result requires review and does not authorize saving', () => {
  const p=prepared(), r=validator.handler({source_json:p.source_json,extraction:JSON.stringify(model())}).result;
  assert.equal(r.ok,true); assert.equal(r.can_save,false);
  assert.ok(r.items[0].notice.needs_confirmation.includes('source_review'));
  assert.ok(r.items[0].notice.needs_confirmation.includes('estimated_minutes'));
});
test('fabricated quotes, extra fields and unsupported kinds fail', () => {
  for(const mutation of [m=>m.items[0].notice.source_spans[0].quote='不存在的时间',
    m=>m.items[0].notice.user_id='someone-else', m=>m.items[0].kind='deadline']) {
    const m=model(); mutation(m);
    assert.throws(()=>validator.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}));
  }
});
test('unread trailing content is explicitly blocked', () => {
  const p=inputContext.handler({source_text:text+'还需参加另一场活动。',source_ref:'self-authored',reference_at:''});
  const r=validator.handler({source_json:p.source_json,extraction:JSON.stringify(model())}).result;
  assert.equal(r.ok,false); assert.ok(r.coverage.uncovered_character_indices.length>0);
});
test('duplicate keys including escaped spellings are rejected before use', () => {
  const p=prepared(), raw=JSON.stringify(model());
  for (const injected of [raw.replace('"kind":','"kind":"event_conflict","kind":'),
    raw.replace('"kind":','"ki\\u006ed":"event_conflict","kind":')]) {
    assert.throws(()=>validator.handler({source_json:p.source_json,extraction:injected}),/DUPLICATE_KEY/);
  }
});
test('invalid calendar dates cannot roll over silently', () => {
  const m=model(); m.items[0].notice.due.at='2026-02-30T10:10:00+08:00';
  assert.throws(()=>validator.handler({source_json:prepared().source_json,extraction:JSON.stringify(m)}),/INVALID_TIME/);
});
test('single-string school adapter rejects foreign fields and non-fictional input', () => {
  const source={source_text:text,source_ref:'self-authored',reference_at:null,fictional_data_confirmed:true};
  const result=schoolInput.handler({notice_input:JSON.stringify(source)});
  assert.equal(JSON.parse(result.source_json).source_text,text);
  assert.deepEqual(JSON.parse(result.model_input).source_segments,[text]);
  for(const bad of [{...source,owner:'other'},{...source,fictional_data_confirmed:false},
    {...source,source_text:''},{...source,reference_at:'today'}]) {
    assert.throws(()=>schoolInput.handler({notice_input:JSON.stringify(bad)}));
  }
});
test('validated transport preserves original model text for the backend', () => {
  const p=prepared(), raw=JSON.stringify(model());
  const result=validator.handler({source_json:p.source_json,extraction:raw});
  assert.equal(JSON.parse(result.query_json).model_output,raw);
  assert.equal(JSON.parse(result.query_json).fictional_data_confirmed,true);
  assert.equal(Object.hasOwn(JSON.parse(result.query_json),'owner'),false);
});
