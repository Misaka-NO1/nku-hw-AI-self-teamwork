import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
test('time selection follows the user and midnight is normalized before calling the tool', () => {
  for (const path of ['./calendar-time-agent-append.txt', './personal-task-agent-append.txt', '../../prompts/main.md']) {
    const text = read(path);
    assert.match(text, /推荐空档不是保存白名单|推荐空档是建议，不是保存白名单/);
    assert.match(text, /15:00—17:00/);
    assert.match(text, /YYYY-MM-DDTHH:mm:ss\+08:00/);
    assert.match(text, /次日00:00|次日零点/);
    assert.match(text, /422/);
  }
  assert.doesNotMatch(read('./notice-free-window-agent-append.txt'), /用户指定子区间必须完全落在当前空档内/);
});
test('draft, explicit confirmation and readback are still required', () => {
  const text = read('./calendar-time-agent-append.txt');
  assert.match(text, /下一轮本人明确确认/);
  assert.match(text, /不能编造草稿回执或成功记录/);
});
