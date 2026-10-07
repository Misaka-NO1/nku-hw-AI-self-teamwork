import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const spec = JSON.parse(readFileSync(new URL('./personal-task-tools.openapi.json', import.meta.url), 'utf8'));
const prompt = readFileSync(new URL('./personal-task-agent-append.txt', import.meta.url), 'utf8');
function resolve(x) {
  if (!x?.$ref) return x;
  return x.$ref.split('/').slice(1).reduce((a, k) => a[k], spec);
}
function walk(x) {
  if (Array.isArray(x)) return x.forEach(walk);
  if (!x || typeof x !== 'object') return;
  if (x.$ref) assert.ok(resolve(x), x.$ref);
  Object.values(x).forEach(walk);
}
function data(path, method) {
  const envelope = resolve(spec.paths[path][method].responses['200'].content['application/json'].schema);
  assert.equal(envelope.properties.ok.type, 'boolean');
  assert.ok(resolve(envelope.properties.error).properties.message);
  assert.ok(resolve(envelope.properties.meta).properties.request_id);
  return resolve(envelope.properties.data).properties;
}
test('OpenAPI references resolve and paths use the existing server', () => {
  walk(spec);
  assert.equal(Object.keys(spec.paths).length, 3);
  assert.equal(spec.servers[0].url, 'https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com');
});
test('model cannot supply an owner, workspace or token in tool inputs', () => {
  for (const [path, method] of [['/oauth/tasks/entries/drafts','post'], ['/oauth/tasks/entries/commit','post']]) {
    const input = resolve(spec.paths[path][method].requestBody.content['application/json'].schema);
    assert.deepEqual(Object.keys(input.properties), ['query_json']);
    assert.deepEqual(input.required, ['query_json']);
    assert.equal(input.additionalProperties, false);
  }
  assert.equal(spec.paths['/oauth/tasks/entries'].get.requestBody, undefined);
});
test('school schema preserves draft identity and all selected ranges', () => {
  const d = data('/oauth/tasks/entries/drafts','post');
  for (const k of ['draft_id','payload_hash','content','saved','requires_user_confirmation']) assert.ok(d[k]);
  const c = resolve(d.content).properties;
  assert.ok(c.reminder_at && c.due_date && c.due_at);
  assert.equal(c.estimated_minutes, undefined);
  assert.equal(resolve(c.scheduled_slots.items).properties.end.type, 'string');
});
test('commit output cannot drop actual save/readback proof', () => {
  const d = data('/oauth/tasks/entries/commit','post');
  for (const k of ['saved','readback_verified','calendar_url','background_push','conflicts_checked']) assert.ok(d[k]);
  const item = resolve(d.item).properties;
  assert.ok(item.task_id && item.status && item.scheduled_slots);
  assert.ok(resolve(item.notice).properties.title);
});
test('list exposes task identity, reminder point and multiple ranges', () => {
  const d = data('/oauth/tasks/entries','get');
  const item = resolve(d.items.items).properties;
  assert.ok(item.task_id && item.reminder_at && item.scheduled_slots);
  assert.equal(d.calendar_url.type, 'string');
});

test('independent reminder shortcut reads actual own records without writing', () => {
  const menu = JSON.parse(readFileSync(new URL('./agent-six-module-menu.json', import.meta.url), 'utf8'));
  assert.equal(menu.shortcuts.length, 6);
  assert.equal(menu.reminder_entry.name, '查看待办时间');
  assert.ok(menu.reminder_entry.message.includes('只读'));
  for (const word of ['独立快捷入口','每一行一个项目','排除completed/cancelled','calendar_url','不只介绍模块']) assert.ok(prompt.includes(word), word);
});
test('prompt requires separate human confirmation and actual readback', () => {
  for (const word of ['上一轮已经展示草稿','此轮用户明确确认','readback_verified=true','通知正文','background_push=false','周内12:00—14:00','最多8段','不包含个人标识']) assert.ok(prompt.includes(word), word);
});
test('school multi-turn history retains the real draft receipt, never guesses missing IDs', () => {
  for (const word of ['不保证保留隐藏工具输出','逐字展示实际draft_id和payload_hash','最近一次已展示回执','等待用户重新确认','不擅自扩展到DDL当天']) assert.ok(prompt.includes(word), word);
  assert.ok(!prompt.includes('不向用户展示技术ID/hash'));
});
