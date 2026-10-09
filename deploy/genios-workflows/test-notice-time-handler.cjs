const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, 'notice-time-fixture-handler.js'), 'utf8'), ctx, {timeout: 1000});
for (const kind of ['event', 'deadline']) {
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, `../../fixtures/time-${kind}-query.demo.json`), 'utf8'));
  const actual = ctx.handler({fixture_id: `notice-${kind}.demo`});
  assert.deepEqual(JSON.parse(actual.query_json), fixture);
  assert.equal(actual.query_json, JSON.stringify(fixture));
  assert.equal(ctx.handler({fixture_id: `notice-${kind}.demo`}).query_json, actual.query_json);
}
for (const input of [null, undefined, {}, {fixture_id: 'notice-ambiguous.demo'}, {fixture_id: 'unknown'},
  {fixture_id: ['notice-event.demo']}, {fixture_id: 'notice-event.demo.json'}, {fixture_id: '__proto__'}]) {
  assert.throws(() => ctx.handler(input), /NOTICE_TIME_NOT_READY/);
}
console.log('PASS: 14 checks, exact two time queries, stable single serialization; ambiguous, unknown and bad-type inputs closed.');
console.log('LOCAL_ONLY: no actual time tool or school execution claimed.');
