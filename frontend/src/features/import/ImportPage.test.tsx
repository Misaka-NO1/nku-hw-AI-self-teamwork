// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import fixture from "../../../../fixtures/timetable.demo.json";
import ImportPage from "./ImportPage";
import type { TimetableImport } from "@campus/import-core";

// Fictional course region with the same shape as an EAMS extension JSON.
const observation={origin:"https://eamis.nankai.edu.cn",pathname:"/eams/courseTableForStd!courseTable.action",frameOrigin:null,tableHeaders:["课程条目","星期","节次"],rows:[["测试课程(0999) (测试教师)(1-4,示例教室)","星期一","1-2"]],selectedTerm:"测试学年1学期",selectedWeeks:[],hasPagination:false,hasVirtualRows:false};
let host:HTMLDivElement,root:Root;
beforeEach(()=>{vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);host=document.createElement("div");document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();});
async function mount(calendar?:TimetableImport["term"]){const preview=vi.fn(),confirmed=vi.fn();await act(async()=>root.render(<ImportPage calendar={calendar} datasetKind="personal" onPreview={preview} onConfirmed={confirmed}/>));return {preview,confirmed};}
function latestPreview(preview:ReturnType<typeof vi.fn>){return preview.mock.calls[preview.mock.calls.length-1]?.[0];}
function file(content:string,name="timetable-import.json"){const value=new File([content],name);Object.defineProperty(value,"text",{configurable:true,value:async()=>content});return value;}
async function select(value:File,label="教务课表文件") {const input=host.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)!;Object.defineProperty(input,"files",{configurable:true,value:[value]});await act(async()=>input.dispatchEvent(new Event("change",{bubbles:true})));}
async function fill(label:string,value:string){const wrapper=Array.from(host.querySelectorAll("label")).find(l=>l.textContent?.startsWith(label))!;const input=wrapper.querySelector<HTMLInputElement|HTMLTextAreaElement>("input,textarea")!;await act(async()=>{Object.getOwnPropertyDescriptor(input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,"value")!.set!.call(input,value);input.dispatchEvent(new Event("input",{bubbles:true}));});}
async function click(text:string){await act(async()=>Array.from(host.querySelectorAll("button")).find(b=>b.textContent===text)!.click());}
async function confirmCalendar(){await fill("第一教学周周一","2026-09-07");await click("我已核对，使用这个校历");}
it("retains a course JSON selected before calendar, then automatically parses without uploading",async()=>{
 const {preview,confirmed}=await mount();await select(file(JSON.stringify(observation)));
 expect(host.textContent).toContain("已接收 timetable-import.json");expect(host.textContent).toContain("不需要重新选择文件");
 expect(host.querySelector<HTMLInputElement>('input[placeholder^="例如"]')!.value).toBe("测试学年1学期");
 await confirmCalendar();expect(host.textContent).toContain("共 1 门课程");expect(host.textContent).toContain("预览与核对");
 expect(latestPreview(preview)?.dataset_kind).toBe("personal");expect(confirmed).not.toHaveBeenCalled();
});
it("recognizes misplaced course JSON in the calendar picker and preserves it",async()=>{
 const {preview}=await mount();await select(file(JSON.stringify(observation)),"学期日历 JSON");
 expect(host.textContent).toContain("已自动转入第二步");await confirmCalendar();expect(latestPreview(preview)?.courses).toHaveLength(1);
});
it("calendar JSON also resumes a previously selected course file",async()=>{
 const {preview}=await mount();await select(file(JSON.stringify(observation)));await select(file(JSON.stringify({...fixture.term,calendar_status:"user_confirmed"}),"calendar.json"),"学期日历 JSON");
 expect(latestPreview(preview)?.courses).toHaveLength(1);
});
it("same file can be chosen again and bad JSON gives a nearby alert",async()=>{
 await mount();await select(file("{"));expect(host.textContent).toContain("JSON 解析失败");
 const picker=host.querySelector<HTMLInputElement>('input[aria-label="教务课表文件"]')!;expect(picker.value).toBe("");
 await select(file(JSON.stringify(observation)));expect(host.textContent).not.toContain("JSON 解析失败");await confirmCalendar();expect(host.textContent).toContain("共 1 门课程");
});
it("file read failures are handled and a later retry works",async()=>{
 await mount();const value=file("");Object.defineProperty(value,"text",{value:()=>Promise.reject(new Error("unavailable"))});await select(value);
 expect(host.textContent).toContain("文件读取失败");expect(host.textContent).not.toContain("正在读取文件");
 await select(file(JSON.stringify(observation)));await confirmCalendar();expect(host.textContent).toContain("共 1 门课程");
});
it("an older asynchronous read cannot replace a newer selection",async()=>{
 await mount();let resolve!:(s:string)=>void;const older=file("");Object.defineProperty(older,"text",{value:()=>new Promise<string>(r=>resolve=r)});
 const input=host.querySelector<HTMLInputElement>('input[aria-label="教务课表文件"]')!;Object.defineProperty(input,"files",{configurable:true,value:[older]});await act(async()=>input.dispatchEvent(new Event("change",{bubbles:true})));
 await select(file(JSON.stringify(observation),"newer.json"));await act(async()=>resolve("invalid"));await confirmCalendar();expect(host.textContent).toContain("已解析 newer.json");expect(host.textContent).not.toContain("JSON 解析失败");
});
it("custom bell times affect standard JSON preview and calendar edits retain course edits",async()=>{
 const {preview}=await mount();await select(file(JSON.stringify(fixture)));await confirmCalendar();
 await click("修改学期 / 上课时间");await fill("每节课起止时间",fixture.term.periods.map((p,i)=>i===0 ? "08:10-08:50" : `${p.start}-${p.end}`).join("\n"));await click("我已核对，使用这个校历");
 const result=latestPreview(preview) as TimetableImport;expect(result.term.periods[0]).toMatchObject({start:"08:10",end:"08:50"});
 const title=host.querySelector<HTMLInputElement>(".import-table-scroll input")!;await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")!.set!.call(title,"用户已改课程名");title.dispatchEvent(new Event("input",{bubbles:true}));});
 await click("修改学期 / 上课时间");await click("我已核对，使用这个校历");expect(latestPreview(preview)?.courses[0].title).toBe("用户已改课程名");
});
it("bad calendar dates and overlapping periods do not resume parsing",async()=>{
 const {preview}=await mount();await select(file(JSON.stringify(observation)));await fill("第一教学周周一","2026-09-08");await click("我已核对，使用这个校历");expect(host.textContent).toContain("必须是周一");
 await fill("第一教学周周一","2026-09-07");await fill("每节课起止时间","08:00-09:00\n08:30-09:30");await click("我已核对，使用这个校历");expect(host.textContent).toContain("互不重叠");expect(latestPreview(preview)).toBeNull();
});
const ownedCalendar={...fixture.term,timezone:"Asia/Shanghai" as const,term_id:observation.selectedTerm,calendar_status:"user_confirmed" as const};
it("automatically parses a file with the owner's matching saved calendar, without any upload",async()=>{
 const {preview,confirmed}=await mount(ownedCalendar);
 await select(file(JSON.stringify(observation)));expect(latestPreview(preview)?.courses).toHaveLength(1);
 expect(latestPreview(preview)?.term).toEqual(ownedCalendar);expect(confirmed).not.toHaveBeenCalled();
});
it("a saved calendar arriving after file selection resumes parsing and cannot undo a manual calendar edit",async()=>{
 const {preview,confirmed}=await mount();await select(file(JSON.stringify(observation)));
 await act(async()=>root.render(<ImportPage calendar={ownedCalendar} datasetKind="personal" onPreview={preview} onConfirmed={confirmed}/>));
 expect(latestPreview(preview)?.courses).toHaveLength(1);expect(host.textContent).toContain("已自动沿用本人");
 await click("修改学期 / 上课时间");expect(host.textContent).toContain("我已核对，使用这个校历");
 expect(host.textContent).not.toContain("当前学期：");
});
it("an uploaded standard timetable carries its confirmed calendar and parses on first import",async()=>{
 const {preview,confirmed}=await mount();await select(file(JSON.stringify({...fixture,term:ownedCalendar})));
 expect(latestPreview(preview)?.courses.length).toBeGreaterThan(0);expect(latestPreview(preview)?.term).toEqual(ownedCalendar);
 expect(confirmed).not.toHaveBeenCalled();expect(host.textContent).toContain("自动载入");
});
it("a different term cannot silently inherit the old owner's calendar",async()=>{
 const {preview}=await mount({...ownedCalendar,term_id:"另一个学期"});await select(file(JSON.stringify(observation)));
 expect(latestPreview(preview)).toBeNull();expect(host.textContent).toContain("不能自动套用旧学期");
 expect(host.querySelector('a[href="#import-calendar"]')).not.toBeNull();
 await confirmCalendar();expect(latestPreview(preview)?.courses).toHaveLength(1);
});
it("mobile FileReader fallback works without File.text",async()=>{
 const {preview}=await mount(ownedCalendar);const value=new File([JSON.stringify(observation)],"mobile.json");
 Object.defineProperty(value,"text",{value:undefined});await select(value);
 await act(async()=>{await new Promise<void>(resolve=>setTimeout(resolve,30));});
 expect(latestPreview(preview)?.courses).toHaveLength(1);expect(host.textContent).not.toContain("文件读取失败");
});
it("accepts UTF-8 BOM exports instead of reporting invalid JSON",async()=>{
 const {preview}=await mount(ownedCalendar);await select(file("\uFEFF"+JSON.stringify(observation)));
 expect(latestPreview(preview)?.courses).toHaveLength(1);expect(host.textContent).not.toContain("JSON 解析失败");
});
it("an unconfirmed calendar inside JSON still needs review",async()=>{
 const {preview}=await mount();await select(file(JSON.stringify({...fixture,term:{...ownedCalendar,calendar_status:"needs_confirmation"}})));
 expect(latestPreview(preview)).toBeNull();expect(host.textContent).toContain("确认后会自动解析");
});
