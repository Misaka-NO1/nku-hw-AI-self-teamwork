// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { DEGREE_PLAN_URL, extractDegreePlanFromDoc } from "@campus/import-core";
import { registerDegreeContent } from "../src/degree-content";
import { isAppUrl, isDegreePageUrl } from "../src/config";
import { isSenderAllowed } from "../src/messages";
import { registerAppBridge } from "../src/app-bridge";
const html = '<table><tr><th>课程序号</th><th>课程名称</th><th>要求学分</th><th>实修学分</th><th>成绩</th><th>是否通过</th><th>备注</th></tr><tr><td colspan="2">通识选修课</td><td>14</td><td>2</td><td colspan="3">缺学分</td></tr><tr><td>TEST001</td><td>虚构课程</td><td>2</td><td>2</td><td>通过</td><td>是</td><td></td></tr></table>';
afterEach(() => { document.body.innerHTML = ""; });
it("uses exact plan path and origin; refuses lookalike/grade/other plan paths", () => {
  expect(isDegreePageUrl(DEGREE_PLAN_URL)).toBe(true);
  for (const url of [DEGREE_PLAN_URL+"/evil",DEGREE_PLAN_URL+"other",DEGREE_PLAN_URL.replace("eamis.nankai.edu.cn","evil.invalid"),"https://eamis.nankai.edu.cn/eams/grades.action"]) expect(isDegreePageUrl(url)).toBe(false);
  expect(isAppUrl("https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com/tools/degree")).toBe(true);
});
it("plan observations cannot come from timetable/app/other extension frames", () => {
  const message = {type:"degree-plan-observation" as const,payload:{}};
  const check = (sender:unknown) => isSenderAllowed(message,sender as never,"ext",()=>true,()=>true,isDegreePageUrl);
  expect(check({id:"ext",url:DEGREE_PLAN_URL,tabUrl:DEGREE_PLAN_URL})).toBe(true);
  expect(check({id:"other",url:DEGREE_PLAN_URL})).toBe(false);
  expect(check({id:"ext",url:"https://evil.invalid",tabUrl:DEGREE_PLAN_URL})).toBe(false);
  expect(check({id:"ext",url:"https://eamis.nankai.edu.cn/eams/courseTableForStd"})).toBe(false);
});
it("mounts a button but sends no data until a deliberate click/message", async () => {
  document.body.innerHTML=html;
  const sendMessage=vi.fn().mockResolvedValue({ok:true}); const listeners: Array<(raw:unknown,sender:unknown,respond:unknown)=>unknown> = [];
  const chromeApi={runtime:{id:"ext",sendMessage,onMessage:{addListener:vi.fn(fn=>listeners.push(fn))}}} as unknown as typeof chrome;
  registerDegreeContent(chromeApi,document,DEGREE_PLAN_URL);
  expect(sendMessage).not.toHaveBeenCalled(); expect(document.getElementById("campus-degree-import-host")).not.toBeNull();
  const create=vi.fn().mockReturnValue('blob:test');
  vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:create,revokeObjectURL:vi.fn()}));
  const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
  const respond=vi.fn(); listeners[0]({type:"extract-visible-degree-plan"},{id:"ext"},respond);
  await vi.waitFor(()=>expect(respond).toHaveBeenCalledWith({ok:true}));
  expect(sendMessage).not.toHaveBeenCalled(); expect(create).toHaveBeenCalled(); expect(click).toHaveBeenCalled();
  click.mockRestore();vi.unstubAllGlobals();
});
it("does not mount or listen on login/unsupported pages", () => {
  const addListener=vi.fn(); const api={runtime:{id:"ext",onMessage:{addListener}}} as unknown as typeof chrome;
  document.body.innerHTML='<input type="password">'+html;
  registerDegreeContent(api,document,DEGREE_PLAN_URL); expect(addListener).not.toHaveBeenCalled();
  expect(document.getElementById("campus-degree-import-host")).toBeNull();
});
it("degree bridge waits for React, does not consume schedule ready or emit schedule data", async () => {
  const win={location:{pathname:"/tools/degree"},listeners:new Map<string,EventListener>(),
    addEventListener(type:string, listener:EventListener){this.listeners.set(type,listener);},
    dispatchEvent:vi.fn(function(this:{listeners:Map<string,EventListener>},event:Event){this.listeners.get(event.type)?.(event);return true;})};
  const sendMessage=vi.fn().mockResolvedValue({ok:true,observation:{kind:"degree_plan_inventory"}});
  registerAppBridge({runtime:{sendMessage}} as unknown as typeof chrome,win as unknown as Window);
  win.dispatchEvent(new Event("campus:schedule-import-ready")); expect(sendMessage).not.toHaveBeenCalled();
  win.dispatchEvent(new Event("campus:degree-import-ready")); await Promise.resolve();
  expect(win.dispatchEvent.mock.calls.map(([event])=>event.type)).toContain("campus:degree-plan-observation");
  expect(win.dispatchEvent.mock.calls.map(([event])=>event.type)).not.toContain("campus:schedule-observation");
});
