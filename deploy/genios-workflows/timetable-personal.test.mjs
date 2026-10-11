import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const prompt=readFileSync(new URL('./timetable-personal-agent-append.txt',import.meta.url),'utf8');
test('uses actual owned records and actual dataset_kind',()=>{for(const text of ['实际调用','read_my_demo_records','schedule.timetable.dataset_kind','dataset_kind=demo','不是实际课表来源判据','401/403','同一 owner']) assert.ok(prompt.includes(text));});
test('course upload and editable bell times remain an explicit save workflow',()=>{for(const text of ['第二步：选择课表文件','不是 Agent 聊天上传框','自动解析','逐节修改','不代表上传或保存','明确确认保存并读回','不能直接跨站']) assert.ok(prompt.includes(text));});
test('personal source policy overrides legacy disclaimers without relabeling fixtures',()=>{for(const text of ['覆盖所有','不再附加','实际读取','确为测试夹具','不冒称官方']) assert.ok(prompt.includes(text));});
test('task and notice templates do not restore unconditional demo restrictions',()=>{
  for(const file of ['personal-task-agent-append.txt','notice-free-window-agent-append.txt','notice-readonly-agent-append.txt','notice-schedule-agent-append.txt']){
    const text=readFileSync(new URL(file,import.meta.url),'utf8');
    for(const obsolete of ['课表仍是已明确标注的虚拟演示课表','真实个人教务仍未接通','真实个人教务尚未接通','本人授权的虚构演示课表','本人授权演示课表']) assert.ok(!text.includes(obsolete),`${file}: ${obsolete}`);
  }
});
