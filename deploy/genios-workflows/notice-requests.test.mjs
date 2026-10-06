import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const reader={}, checker={};
vm.runInNewContext(readFileSync(new URL('./notice-read-request.js',import.meta.url),'utf8'),reader);
vm.runInNewContext(readFileSync(new URL('./notice-check-request.js',import.meta.url),'utf8'),checker);
const source={source_text:'一份全新的虚构通知',source_ref:'本次原文',reference_at:null};
const raw='{"items":[],"unclassified":["一份全新的虚构通知"]}';
const read=()=>reader.handler({source_json:JSON.stringify(source),extraction:raw}).query_json;
test('source/model text remain unchanged; no owner or fixture id',()=>{
  const q=JSON.parse(read()); assert.equal(q.source_text,source.source_text);assert.equal(q.model_output,raw);
  assert.equal(Object.hasOwn(q,'workspace_ref'),false); assert.equal(Object.hasOwn(q,'fixture_id'),false);
});
test('nulls, arrays and explicit fields map to the same check transport',()=>{
  const q=checker.handler({read_request_json:read(),item_id:'model-item',user_confirmations_json:'{"source_review":false,"estimated_minutes":null}',
    window_json:'{"start":"s","end":"e"}',available_windows_json:'[]'}).query_json;
  assert.equal(JSON.parse(q).user_confirmations.estimated_minutes,null);
  assert.deepEqual(JSON.parse(q).available_windows,[]);
});
test('missing user choices are not invented',()=>{
  assert.throws(()=>checker.handler({read_request_json:read(),item_id:'model-item'}),/MISSING_EXPLICIT_INPUT/);
});
test('raw duplicate keys are retained for backend strict rejection',()=>{
  const q=checker.handler({read_request_json:read(),item_id:'model-item',user_confirmations_json:'{"estimated_minutes":20,"estimated_minutes":60}',
    window_json:'{"start":"s","end":"e"}',available_windows_json:'[]'}).query_json;
  assert.ok(q.includes('"estimated_minutes":20,"estimated_minutes":60'));
});
