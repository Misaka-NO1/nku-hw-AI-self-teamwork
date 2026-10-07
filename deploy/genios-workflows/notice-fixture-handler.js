// Closed, public, fictitious inputs only. Not an identity or a saved task.
function handler(params) {
  const entries = {
    'notice-event.demo': {
      notice_id: 'demo-notice-01', title: '虚构活动通知', published_at: '2026-09-19T09:00:00+08:00',
      sources: [{source_ref: '自创测试通知01', text: '测试活动于2026年9月21日09:20至10:20举行。'}]
    },
    'notice-deadline.demo': {
      notice_id: 'demo-notice-02', title: '虚构截止任务', published_at: '2026-09-19T09:00:00+08:00',
      sources: [{source_ref: '自创测试通知02', text: '请在2026年9月21日10:10前完成测试提交。'},
        {source_ref: '测试用户确认', text: '用户确认预计用时20分钟，最早09:40开始。'}]
    },
    'notice-ambiguous.demo': {
      notice_id: 'demo-notice-03', title: '缺少发布日期的虚构通知', published_at: null,
      sources: [{source_ref: '自创测试通知03', text: '请于本周五前提交材料。'}]
    }
  };
  if (!params || typeof params.fixture_id !== 'string'
      || !Object.prototype.hasOwnProperty.call(entries, params.fixture_id)) {
    throw new Error('UNKNOWN_FIXTURE: only three fixed public fictitious notices are supported');
  }
  const entry = entries[params.fixture_id];
  return {fixture_id: params.fixture_id, model_input: JSON.stringify({
    dataset_kind: 'demo', notice_id: entry.notice_id, title: entry.title,
    published_at: entry.published_at, extracted_at: '2026-09-19T12:00:00+08:00',
    timezone: 'Asia/Shanghai', sources: entry.sources
  })};
}
