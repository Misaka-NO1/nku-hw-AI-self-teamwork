const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function load(name) {
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, name), 'utf8'), ctx, {timeout: 1000});
  return input => JSON.parse(JSON.stringify(ctx.handler(input)));
}
const input = load('notice-fixture-handler.js');
const guard = load('notice-preview-guard.js');
let checks = 0;
for (const kind of ['event', 'deadline', 'ambiguous']) {
  const id = `notice-${kind}.demo`;
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, `../../fixtures/${id}.json`), 'utf8'));
  const source = JSON.parse(input({fixture_id: id}).model_input);
  assert.equal(source.notice_id, fixture.notice_id); checks++;
  for (const span of fixture.source_spans) {
    assert.ok(source.sources.some(s => s.source_ref === span.source_ref && s.text === span.quote)); checks++;
  }
  const result = guard({fixture_id: id, extraction: JSON.stringify(fixture)});
  assert.deepEqual(result.result.notice, fixture); checks++;
  assert.equal(result.result.saved, false); checks++;
  if (kind === 'ambiguous') {
    assert.equal(result.result.status, 'needs_confirmation'); checks++;
    assert.equal(result.query_json, ''); checks++;
    for (const needs of [[], ['published_at_or_explicit_reference_date']]) {
      const derived = guard({fixture_id: id, extraction: JSON.stringify({...fixture, needs_confirmation: needs})});
      assert.deepEqual(derived.result.notice, fixture); checks++;
      assert.equal(derived.result.status, 'needs_confirmation'); checks++;
      assert.deepEqual(derived.result.model_confirmation_omissions, fixture.needs_confirmation.filter(k => !needs.includes(k))); checks++;
      assert.equal(derived.query_json, ''); checks++;
    }
  } else {
    const time = JSON.parse(fs.readFileSync(path.join(__dirname, `../../fixtures/time-${kind}-query.demo.json`), 'utf8'));
    assert.deepEqual(JSON.parse(result.query_json), time); checks++;
  }
  const attacks = [
    {...fixture, task_id: 'fake-saved'}, {...fixture, timezone: 'UTC'}, {...fixture, estimated_minutes: 0},
    {...fixture, estimated_minutes: 60},
    {...fixture, materials: ['未授权附件']}, {...fixture, source_spans: []}, {...fixture, published_at: 'null'},
    {...fixture, event: {...fixture.event, end: '2026-09-21T23:59:00+08:00'}},
    {...fixture, due: {...fixture.due, at: '2026-09-25T23:59:00+08:00'}},
    {...fixture, due: {...fixture.due, date: '2026-09-18', precision: 'date_only'}},
    {...fixture, needs_confirmation: ['anything']}
  ];
  for (const extraction of attacks.map(JSON.stringify).concat([
    '```json\n' + JSON.stringify(fixture) + '\n```', '{"title":"x",' + JSON.stringify(fixture).slice(1),
    'null', '{}', '[]', JSON.stringify(fixture) + ' trailing', 'x'.repeat(6001)
  ])) {
    const rejected = guard({fixture_id: id, extraction});
    assert.equal(rejected.result.status, 'extraction_check_failed'); checks++;
    assert.equal(rejected.result.notice, null); checks++;
    assert.equal(rejected.query_json, ''); checks++;
  }
  const reordered = Object.fromEntries(Object.entries(fixture).reverse());
  assert.deepEqual(guard({fixture_id: id, extraction: JSON.stringify(reordered)}).result.notice, fixture); checks++;
}
for (const bad of [undefined, null, {}, {fixture_id: 'unknown'}, {fixture_id: '__proto__'}, {fixture_id: 'constructor'},
  {fixture_id: null}, {fixture_id: ['notice-event.demo']}]) {
  assert.throws(() => input(bad), /UNKNOWN_FIXTURE/); checks++;
  assert.throws(() => guard(bad), /UNKNOWN_FIXTURE/); checks++;
}
console.log(`PASS: ${checks} checks, exact NoticeDraft fixtures/evidence/time queries, malformed and duplicate JSON rejected, unknown IDs closed.`);
console.log('LOCAL_ONLY: no LLM, school workflow, trusted identity, time-check execution or database write is claimed by this test.');
