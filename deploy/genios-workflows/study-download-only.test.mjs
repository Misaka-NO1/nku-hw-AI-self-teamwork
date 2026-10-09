import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('study templates disable teaching even on explicit requests', () => {
  for (const path of ['../../prompts/main.md', '../../prompts/study-answer.md', './study-agent-prompt-append.txt']) {
    const text = read(path);
    assert.match(text, /即使用户明确|用户明确请求也不恢复/);
    assert.match(text, /不调用\s*`?WF_StudyAnswer|不绑定或调用\s*`WF_StudyAnswer/);
    assert.match(text, /不检索\s*`?KB_Study|不绑定或检索\s*`KB_Study/);
    assert.doesNotMatch(text, /只有用户明确要求.*才使用WF_StudyAnswer|明确讲解时才根据工作流|用户明确要求.*才调用StudyAnswer/);
  }
});

test('file delivery and full library entry remain available', () => {
  for (const path of ['../../prompts/main.md', '../../prompts/study-answer.md', './study-agent-prompt-append.txt']) {
    const text = read(path);
    assert.match(text, /platform_search_study_materials/);
    assert.match(text, /download_url/);
    assert.match(text, /https:\/\/nku-campus-public-content-308235-6-1467707525\.sh\.run\.tcloudbase\.com\/tools\/study/);
  }
});
