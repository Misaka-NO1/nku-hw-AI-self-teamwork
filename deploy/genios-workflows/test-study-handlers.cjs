const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
function load(file) { const sandbox = {}; vm.runInNewContext(fs.readFileSync(path.join(__dirname, file), 'utf8'), sandbox); return p => JSON.parse(JSON.stringify(sandbox.handler(p))); }
const context = load('study-context-handler.js');
const guard = load('study-answer-guard.js');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'knowledge/study/library/upload-manifest.json'), 'utf8'));
const id = 'study-s2-programming-f076c553a310a022';
const text = fs.readFileSync(path.join(root, 'knowledge/study/exports/year1', id + '.md'), 'utf8');
const chunks = text.split(/^## /m).slice(1).map(chunk => '## ' + chunk);
const item = {output: chunks.find(chunk => chunk.startsWith('## PDF 第 3 页 · 片段 1')), metadata: {document_name: id + '.md', document_url: 'https://unused.invalid/secret'}};
const input = {course_id: 'y1-s2-programming', question: '初始化列表', outputList: [item]};
let checks = 0;
function check(test) { test(); checks++; }
check(() => assert.equal(context(input).status, 'grounded'));
check(() => assert.equal(JSON.parse(context(input).sources_json)[0].page, 3));
check(() => assert.equal(context({...input, outputList: [item, item]}).status, 'grounded'));
check(() => assert.equal(JSON.parse(context({...input, outputList: [item, item]}).sources_json).length, 1));
check(() => assert.equal(context({...input, course_id: 'y1-s1-programming'}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, course_id: 'demo-CS101'}).status, 'unknown_course'));
check(() => assert.equal(context({...input, outputList: [{...item, output: text.split(/^## /m)[0]}]}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, outputList: [{...item, output: item.output.replace('version: sha256:f076', 'version: sha256:ffff')}]}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, outputList: [{...item, output: item.output.replace('#page=3', '#page=8')}]}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, outputList: [{...item, output: item.output + '\ncourse_id: y1-s1-programming'}]}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, outputList: [{...item, metadata: {document_name: 'other.md'}}]}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, outputList: [{...item, output: item.output.replace(/_/g, '\\_')}]}).status, 'grounded'));
check(() => assert.throws(() => context({...input, question: '', outputList: []}), /INVALID_STUDY_INPUT/));
check(() => assert.throws(() => context({...input, outputList: new Array(21).fill(item)}), /INVALID_STUDY_INPUT/));
check(() => assert.ok(!context(input).sources_json.includes('unused.invalid')));
const inlineItem = {...item, output: '> ' + id + '.md\n> PDF 第 3 页 · 片段 1\n\n' + item.output.replace(/^(material_id|version|course_id|chunk_id|source_label|page_label|source_excerpt_ref|extraction_method):([^\n]*)\n/gm, '$1:$2 ')};
check(() => assert.equal(context({...input, outputList: [inlineItem]}).status, 'grounded'));
check(() => assert.equal(JSON.parse(context({...input, outputList: [inlineItem]}).sources_json)[0].page, 3));
check(() => assert.equal(context({...input, outputList: [{...inlineItem, output: inlineItem.output + '\ncourse_id: y1-s1-programming'}]}).status, 'no_matching_body'));
check(() => assert.equal(context({...input, outputList: [{...inlineItem, output: inlineItem.output.replace('#page=3', '#page=8')}]}).status, 'no_matching_body'));
const accepted = context(input);
check(() => assert.equal(context({...input, material_id: id}).status, 'grounded'));
check(() => assert.equal(context({...input, material_id: null}).status, 'grounded'));
check(() => assert.equal(context({...input, material_id: 'study-s2-programming-not-exist-999'}).status, 'unknown_material'));
check(() => assert.equal(context({...input, material_id: 'study-s1-programming-7267a3cd0b2e11aa'}).status, 'unknown_material'));
check(() => assert.equal(context({...input, material_id: 'study-s2-physics-c6b936374c8ae864'}).status, 'unknown_material'));
check(() => assert.equal(context({...input, material_id: 'study-s2-programming-ecb1b840316f954b'}).status, 'no_matching_body'));
check(() => assert.throws(() => context({...input, material_id: {id}}), /INVALID_STUDY_INPUT/));
check(() => assert.equal(guard({...context({...input, material_id: 'unknown'}), answer: '编造正文'}).result.status, 'unknown_material'));
check(() => assert.equal(guard({...accepted, answer: `根据 PDF 第3页，成员在对象创建时初始化。[${id}@3]`}).result.status, 'grounded'));
check(() => assert.equal(guard({...accepted, answer: '没有来源的回答'}).result.status, 'citation_check_failed'));
check(() => assert.equal(guard({...accepted, answer: `[${id}@999]`}).result.status, 'citation_check_failed'));
check(() => {
  const other = {material_id: 'study-s2-programming-ecb1b840316f954b', page: 9};
  assert.equal(guard({...accepted, sources_json: JSON.stringify([...JSON.parse(accepted.sources_json), other]),
    answer: `[${id}@9]`}).result.status, 'citation_check_failed');
});
check(() => assert.equal(guard({...accepted, answer: `[${id}@3] PDF 第999页`}).result.status, 'citation_check_failed'));
check(() => assert.equal(guard({...accepted, answer: `[${id}@3] study-s1-other-unknown`}).result.status, 'citation_check_failed'));
check(() => assert.equal(guard({...accepted, answer: `[${id}@3] https://fabricated.invalid`}).result.status, 'citation_check_failed'));
check(() => assert.equal(guard({...context({...input, course_id: 'demo-CS101'}), answer: '编造正文'}).result.sources.length, 0));
check(() => assert.ok(!guard({...context({...input, outputList: []}), answer: '编造正文'}).result.answer.includes('编造正文')));
check(() => assert.throws(() => guard({...accepted, answer: ''}), /INVALID_STUDY_ANSWER/));
check(() => {
  const ids = manifest.files.map(row => row.material_id);
  assert.ok(!ids.includes('study-s1-programming-7267a3cd0b2e11aa'));
  for (const row of manifest.files) {
    const data = fs.readFileSync(path.join(root, row.file_ref), 'utf8');
    const candidates = data.split(/^## /m).slice(1).map(chunk => ({output: '## ' + chunk, metadata: {document_name: row.material_id + '.md'}}));
    assert.ok(candidates.length > 0);
    const result = context({course_id: row.tags.course_id, question: '公开材料', outputList: candidates.slice(0, 20)});
    assert.equal(result.status, 'grounded', row.material_id);
    assert.equal(JSON.parse(result.sources_json)[0].version, row.material_version);
  }
});
console.log(`${checks} study workflow checks passed; all 33 manifest files matched.`);
