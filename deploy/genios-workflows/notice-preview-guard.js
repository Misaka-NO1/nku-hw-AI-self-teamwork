// Closed-fixture semantic oracle: strict extraction acceptance, never a write tool.
function handler(params) {
  const emptyEvent = {start: null, end: null, date: null, precision: 'unknown'};
  const emptyDue = {at: null, date: null, precision: 'unknown'};
  const base = {schema_version: '1.0.0', extracted_at: '2026-09-19T12:00:00+08:00',
    timezone: 'Asia/Shanghai', materials: []};
  const expected = {
    'notice-event.demo': Object.assign({}, base, {
      notice_id: 'demo-notice-01', title: '虚构活动通知', published_at: '2026-09-19T09:00:00+08:00',
      event: {start: '2026-09-21T09:20:00+08:00', end: '2026-09-21T10:20:00+08:00', date: null, precision: 'datetime'},
      due: emptyDue, estimated_minutes: null, earliest_start: null,
      source_spans: [{field: 'event', quote: '测试活动于2026年9月21日09:20至10:20举行。', source_ref: '自创测试通知01'}],
      needs_confirmation: []
    }),
    'notice-deadline.demo': Object.assign({}, base, {
      notice_id: 'demo-notice-02', title: '虚构截止任务', published_at: '2026-09-19T09:00:00+08:00',
      event: emptyEvent, due: {at: '2026-09-21T10:10:00+08:00', date: null, precision: 'datetime'},
      estimated_minutes: 20, earliest_start: '2026-09-21T09:40:00+08:00',
      source_spans: [{field: 'due', quote: '请在2026年9月21日10:10前完成测试提交。', source_ref: '自创测试通知02'},
        {field: 'estimated_minutes', quote: '用户确认预计用时20分钟，最早09:40开始。', source_ref: '测试用户确认'}],
      needs_confirmation: []
    }),
    'notice-ambiguous.demo': Object.assign({}, base, {
      notice_id: 'demo-notice-03', title: '缺少发布日期的虚构通知', published_at: null,
      event: emptyEvent, due: emptyDue, estimated_minutes: null, earliest_start: null,
      source_spans: [{field: 'due', quote: '请于本周五前提交材料。', source_ref: '自创测试通知03'}],
      needs_confirmation: ['published_at_or_explicit_reference_date', 'due_time', 'estimated_minutes']
    })
  };
  if (!params || typeof params.fixture_id !== 'string'
      || !Object.prototype.hasOwnProperty.call(expected, params.fixture_id)) throw new Error('UNKNOWN_FIXTURE');
  function reject() {
    return {result: {status: 'extraction_check_failed', dataset_kind: 'demo', notice: null,
      saved: false, answer: '通知提取未通过固定夹具、字段及原文证据校验；不展示不可靠草稿，不检查时间，不保存任务。'}, query_json: ''};
  }
  if (typeof params.extraction !== 'string' || params.extraction.length > 6000) return reject();
  // Parse strict JSON, rejecting duplicate keys before semantic validation.
  function parseStrict(text) {
    let i = 0;
    function ws() { while (/\s/.test(text[i] || '') && i < text.length) i++; }
    function string() {
      const start = i++;
      while (i < text.length) {
        const c = text[i++];
        if (c === '\\') i++;
        else if (c === '"') return JSON.parse(text.slice(start, i));
      }
      throw new Error('INVALID_JSON');
    }
    function value() {
      ws();
      if (text[i] === '{') {
        i++; ws(); const seen = new Set();
        if (text[i] === '}') { i++; return; }
        while (true) {
          ws(); if (text[i] !== '"') throw new Error('INVALID_JSON');
          const key = string(); if (seen.has(key)) throw new Error('DUPLICATE_KEY'); seen.add(key);
          ws(); if (text[i++] !== ':') throw new Error('INVALID_JSON'); value(); ws();
          const end = text[i++]; if (end === '}') return; if (end !== ',') throw new Error('INVALID_JSON');
        }
      }
      if (text[i] === '[') {
        i++; ws(); if (text[i] === ']') { i++; return; }
        while (true) { value(); ws(); const end = text[i++]; if (end === ']') return; if (end !== ',') throw new Error('INVALID_JSON'); }
      }
      if (text[i] === '"') { string(); return; }
      const match = /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(text.slice(i));
      if (!match) throw new Error('INVALID_JSON'); i += match[0].length;
    }
    value(); ws(); if (i !== text.length) throw new Error('INVALID_JSON'); return JSON.parse(text);
  }
  function canonical(value) {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  const notice = expected[params.fixture_id];
  let confirmationOmissions = [];
  try {
    const candidate = parseStrict(params.extraction);
    // Confirmation requirements are an authoritative code policy, not model permission.
    // Never repair malformed JSON, missing source fields, invented dates, or extra keys.
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)
        || !Array.isArray(candidate.needs_confirmation)
        || new Set(candidate.needs_confirmation).size !== candidate.needs_confirmation.length
        || candidate.needs_confirmation.some(key => typeof key !== 'string'
          || !notice.needs_confirmation.includes(key))) return reject();
    const observations = Object.assign({}, candidate);
    const expectedObservations = Object.assign({}, notice);
    delete observations.needs_confirmation;
    delete expectedObservations.needs_confirmation;
    if (canonical(observations) !== canonical(expectedObservations)) return reject();
    confirmationOmissions = notice.needs_confirmation.filter(key => !candidate.needs_confirmation.includes(key));
  } catch (_) { return reject(); }
  let query = null;
  if (!notice.needs_confirmation.length) query = {
    workspace_ref: 'demo-workspace-01', kind: params.fixture_id === 'notice-event.demo' ? 'event_conflict' : 'deadline_feasibility',
    window: {start: '2026-09-21T08:00:00+08:00', end: '2026-09-21T12:00:00+08:00'},
    event: params.fixture_id === 'notice-event.demo' ? notice.event : null,
    due: params.fixture_id === 'notice-deadline.demo' ? notice.due : null,
    estimated_minutes: notice.estimated_minutes, earliest_start: notice.earliest_start,
    allow_split: false, buffers: {before_minutes: 0, after_minutes: 0}
  };
  return {result: {status: notice.needs_confirmation.length ? 'needs_confirmation' : 'validated_preview',
    dataset_kind: 'demo', notice, saved: false, time_check_ready: query !== null,
    confirmation_policy_applied: true, model_confirmation_omissions: confirmationOmissions,
    answer: '仅为固定虚构通知的已校验预览；尚未执行时间检查、建立数据库草稿或保存任务。'},
    query_json: query ? JSON.stringify(query) : ''};
}
