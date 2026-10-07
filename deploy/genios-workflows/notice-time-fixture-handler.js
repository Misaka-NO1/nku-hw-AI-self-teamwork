// Only complete, fixed fictitious examples; no personal workspace or inferred dates.
function handler(params) {
  if (!params || !['notice-event.demo', 'notice-deadline.demo'].includes(params.fixture_id)) {
    throw new Error('NOTICE_TIME_NOT_READY: only the two complete fictitious notices support a time check');
  }
  const event = params.fixture_id === 'notice-event.demo';
  const query = {
    workspace_ref: 'demo-workspace-01', kind: event ? 'event_conflict' : 'deadline_feasibility',
    window: {start: '2026-09-21T08:00:00+08:00', end: '2026-09-21T12:00:00+08:00'},
    event: event ? {start: '2026-09-21T09:20:00+08:00', end: '2026-09-21T10:20:00+08:00', date: null, precision: 'datetime'} : null,
    due: event ? null : {at: '2026-09-21T10:10:00+08:00', date: null, precision: 'datetime'},
    estimated_minutes: event ? null : 20,
    earliest_start: event ? null : '2026-09-21T09:40:00+08:00',
    allow_split: false, buffers: {before_minutes: 0, after_minutes: 0}
  };
  return {fixture_id: params.fixture_id, query_json: JSON.stringify(query)};
}
