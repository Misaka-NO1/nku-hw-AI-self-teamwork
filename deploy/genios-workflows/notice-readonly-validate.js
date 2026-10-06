// Generic structure/evidence guard. A passing result still requires source review.
// This is a code-node candidate, not an installed workflow or a save tool.
function validateReadOnlyNotice(params) {
  const decode = text => {
    const result = JSON.parse(text, (key, value) => {
      if (['__proto__', 'constructor', 'prototype'].includes(key)) throw new Error('UNSAFE_KEY');
      return value;
    });
    // JSON.parse silently overwrites duplicate keys. Inspect the validated JSON
    // tokens too, including escaped spellings of the same key, before using it.
    let at = 0;
    const spaces = () => { while (/\s/.test(text[at] || '') && at < text.length) at++; };
    const string = () => {
      const begin = at++;
      while (at < text.length) {
        if (text[at] === '\\') at += 2;
        else if (text[at++] === '"') break;
      }
      return JSON.parse(text.slice(begin, at));
    };
    const walk = depth => {
      if (depth > 64) throw new Error('JSON_TOO_DEEP');
      spaces();
      if (text[at] === '"') { string(); return; }
      if (text[at] === '{') {
        at++; spaces(); const keys = new Set();
        while (text[at] !== '}') {
          const key = string();
          if (keys.has(key)) throw new Error('DUPLICATE_KEY');
          keys.add(key); spaces(); at++; walk(depth + 1); spaces();
          if (text[at] !== ',') break;
          at++; spaces();
        }
        at++; return;
      }
      if (text[at] === '[') {
        at++; spaces();
        while (text[at] !== ']') {
          walk(depth + 1); spaces();
          if (text[at] !== ',') break;
          at++;
        }
        at++; return;
      }
      while (at < text.length && !/[\s,\]}]/.test(text[at])) at++;
    };
    walk(0);
    return result;
  };
  const source = decode(params.source_json);
  if (typeof source.source_text !== 'string' || source.source_text.length > 20000 || !source.source_text.trim()) {
    throw new Error('INVALID_SOURCE');
  }
  if (typeof params.extraction !== 'string' || params.extraction.length > 120000) throw new Error('INVALID_EXTRACTION');
  const batch = decode(params.extraction);
  const fields = ['schema_version','notice_id','title','published_at','extracted_at','timezone','event','due',
    'estimated_minutes','earliest_start','materials','source_spans','needs_confirmation'];
  const exact = (obj, keys) => obj && !Array.isArray(obj) && typeof obj === 'object'
    && Object.keys(obj).length === keys.length && keys.every(k => Object.hasOwn(obj, k));
  const dt = v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+08:00$/.test(v)
    && Number.isFinite(Date.parse(v))
    && new Date(Date.parse(v) + 8 * 3600000).toISOString().slice(0,19) === v.slice(0,19);
  const day = v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)
    && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0,10) === v;
  const stringArray = a => Array.isArray(a) && a.every(v => typeof v === 'string');
  if (!exact(batch, ['items','unclassified']) || !Array.isArray(batch.items) || batch.items.length > 50
      || !stringArray(batch.unclassified)) throw new Error('INVALID_BATCH');
  const covered = new Array(source.source_text.length).fill(false);
  const cover = quote => {
    if (typeof quote !== 'string' || !quote.trim()) throw new Error('EMPTY_EVIDENCE');
    let found = false;
    // Repeated quotations cover only text actually present in the supplied source.
    for (let from = 0; from < source.source_text.length;) {
      const at = source.source_text.indexOf(quote, from);
      if (at < 0) break;
      found = true;
      for (let i = at; i < at + quote.length; i++) covered[i] = true;
      from = at + quote.length;
    }
    if (!found) throw new Error('FABRICATED_EVIDENCE');
  };
  const ids = new Set();
  const items = batch.items.map((item, index) => {
    if (!exact(item, ['kind','notice']) || !['event_conflict','deadline_feasibility'].includes(item.kind)) throw new Error('INVALID_ITEM');
    const n = item.notice;
    if (!exact(n, fields) || n.schema_version !== '1.0.0' || n.timezone !== 'Asia/Shanghai'
        || typeof n.notice_id !== 'string' || !n.notice_id || n.notice_id.length > 128
        || typeof n.title !== 'string' || !n.title.trim() || ids.has(n.notice_id)) throw new Error('INVALID_NOTICE');
    ids.add(n.notice_id);
    if (!exact(n.event, ['start','end','date','precision']) || !exact(n.due, ['at','date','precision'])
        || !['datetime','date_only','unknown'].includes(n.event.precision)
        || !['datetime','date_only','unknown'].includes(n.due.precision)) throw new Error('INVALID_TIME_SHAPE');
    for (const value of [n.event.start,n.event.end,n.due.at,n.earliest_start,n.published_at]) {
      if (value !== null && !dt(value)) throw new Error('INVALID_TIME');
    }
    for (const value of [n.event.date,n.due.date]) if (value !== null && !day(value)) throw new Error('INVALID_DATE');
    if (n.estimated_minutes !== null && (!Number.isInteger(n.estimated_minutes)
        || n.estimated_minutes < 1 || n.estimated_minutes > 10080)) throw new Error('INVALID_DURATION');
    if (!stringArray(n.materials) || !stringArray(n.needs_confirmation) || !Array.isArray(n.source_spans)) throw new Error('INVALID_FIELDS');
    if (n.event.precision === 'datetime' && (!dt(n.event.start) || !dt(n.event.end)
        || Date.parse(n.event.start) >= Date.parse(n.event.end))) throw new Error('INVALID_EVENT');
    if (n.due.precision === 'datetime' && !dt(n.due.at)) throw new Error('INVALID_DUE');
    if (n.due.precision !== 'datetime' && n.due.at !== null) throw new Error('INCONSISTENT_DUE');
    if (n.event.precision !== 'datetime' && (n.event.start !== null || n.event.end !== null)) throw new Error('INCONSISTENT_EVENT');
    const evidence = {};
    n.source_spans.forEach(span => {
      if (!exact(span,['field','quote','source_ref']) || !fields.includes(span.field)
          || typeof span.source_ref !== 'string' || span.source_ref !== source.source_ref) throw new Error('INVALID_SPAN');
      cover(span.quote);
      (evidence[span.field] ||= []).push(span.quote);
    });
    const needs = new Set([...n.needs_confirmation, 'source_review']);
    const evidenced = field => Array.isArray(evidence[field]) && evidence[field].length > 0;
    if (n.event.precision !== 'unknown' && !evidenced('event')) throw new Error('EVENT_WITHOUT_EVIDENCE');
    if (n.due.precision !== 'unknown' && !evidenced('due')) throw new Error('DUE_WITHOUT_EVIDENCE');
    if (n.estimated_minutes !== null && !evidenced('estimated_minutes')) throw new Error('DURATION_WITHOUT_EVIDENCE');
    if (n.earliest_start !== null && !evidenced('earliest_start')) throw new Error('EARLIEST_WITHOUT_EVIDENCE');
    if (n.materials.some(v => !(evidence.materials || []).some(q => q.includes(v)))) throw new Error('MATERIAL_WITHOUT_EVIDENCE');
    const quotes = n.source_spans.map(s => s.quote).join('\n');
    if (/取消|延期|改期|作废|无需|不用|不必|更正|原定|待定/.test(quotes)) needs.add('changed_or_cancelled_notice');
    if (/明天|今天|后天|本周|下周/.test(quotes) && !source.reference_at && !n.published_at) needs.add('reference_date');
    if (n.event.precision !== 'unknown' && n.due.precision !== 'unknown') needs.add('mixed_actions');
    if (item.kind === 'event_conflict' && n.event.precision !== 'datetime') needs.add('event_time');
    if (item.kind === 'deadline_feasibility') {
      if (n.due.precision !== 'datetime') needs.add('due_time');
      if (n.estimated_minutes === null) needs.add('estimated_minutes');
      if (n.earliest_start === null) needs.add('earliest_start');
    }
    // Evidence existence does not establish semantic agreement. Never auto-calculate
    // from unchecked model dates, even after successful structural validation.
    return {kind:item.kind, notice:{...n, extracted_at:source.extracted_at,
      needs_confirmation:[...needs]}, item_index:index};
  });
  batch.unclassified.forEach(cover);
  const unread = [];
  for (let i=0; i<covered.length; i++) {
    if (!covered[i] && !/\s/.test(source.source_text[i])) unread.push(i);
  }
  const result = {ok:unread.length === 0, batch_version:'notice-model-candidate-v1', items,
    unclassified:batch.unclassified, coverage:{characters_total:covered.length,
      uncovered_character_indices:unread}, needs_confirmation:unread.length ? ['incomplete_reading'] : [],
    status:'review_required', can_save:false};
  return {result, validated_json:JSON.stringify(result),
    query_json:JSON.stringify({source_text:source.source_text, source_ref:source.source_ref,
      reference_at:source.reference_at, model_output:params.extraction, fictional_data_confirmed:true})};
}

// School-only result. Never emit a fictional cloud request for real source text.
function handler(params) {
  const validated = validateReadOnlyNotice(params);
  // Free-form model flags must not manufacture registration or ID requirements.
  const scheduling_clarifications = validated.result.items.map(item => {
    const n = item.notice, fields = [];
    if (item.kind === 'event_conflict') {
      if (n.event.precision !== 'datetime') fields.push('event_interval');
      if (n.source_spans.some(s => s.field === 'event' && /约|大约|预计/.test(s.quote))) fields.push('confirm_estimated_end');
    } else {
      if (n.due.precision !== 'datetime') fields.push('due_time');
      if (n.estimated_minutes === null) fields.push('estimated_minutes');
      if (n.earliest_start === null) fields.push('earliest_start');
    }
    if (n.needs_confirmation.includes('reference_date')) fields.push('reference_date');
    if (n.needs_confirmation.includes('changed_or_cancelled_notice')) fields.push('latest_notice_version');
    return {item_index:item.item_index, title:n.title, fields};
  }).filter(item => item.fields.length);
  return {result:{...validated.result, scheduling_clarifications, source_scope:'user_provided_read_only',
    saved:false, time_check_performed:false}, query_json:''};
}
