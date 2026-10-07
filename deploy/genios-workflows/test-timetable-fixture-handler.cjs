const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const code = fs.readFileSync(path.join(__dirname, 'timetable-fixture-handler.js'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, '../../fixtures/timetable.demo.json'), 'utf8'));
const context = vm.createContext({});
vm.runInContext(code, context, { timeout: 1000 });
const result = context.handler({ fixture_id: 'timetable.demo' });
assert.deepEqual(JSON.parse(result.query_json), fixture);
assert.equal(result.query_json, JSON.stringify(fixture));
assert.equal(result.query_json.length, 1606);
assert.equal(result.fixture_id, 'timetable.demo');
for (let i = 0; i < 3; i++) {
  assert.equal(context.handler({ fixture_id: 'timetable.demo' }).query_json, result.query_json);
}
for (const input of [undefined, null, {}, { fixture_id: 'unknown' },
  { fixture_id: null }, { fixture_id: 'null' }, { fixture_id: ['timetable.demo'] }]) {
  assert.throws(() => context.handler(input), /UNKNOWN_FIXTURE/);
}
console.log('PASS: exact fixture, single serialization, length 1606, stable repeats, unknown IDs rejected.');
console.log('LOCAL_ONLY: this test does not replace school workflow, MCP, or main-Agent acceptance.');
