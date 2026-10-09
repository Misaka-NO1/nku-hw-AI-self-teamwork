import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const prompt=readFileSync(new URL('./timetable-personal-agent-append.txt',import.meta.url),'utf8');
test('uses actual owned records and actual dataset_kind',()=>{for(const text of ['实际调用','read_my_demo_records','schedule.timetable.dataset_kind','dataset_kind=demo','不是实际课表来源判据','401/403','同一 owner']) assert.ok(prompt.includes(text));});
test('course upload and editable bell times remain an explicit save workflow',()=>{for(const text of ['第二步：选择课表文件','不是 Agent 聊天上传框','自动解析','逐节修改','不代表上传或保存','明确确认保存并读回','不能直接跨站']) assert.ok(prompt.includes(text));});
