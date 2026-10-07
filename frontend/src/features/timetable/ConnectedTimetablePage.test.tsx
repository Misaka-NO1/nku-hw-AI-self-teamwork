// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TimetableImport } from "@campus/import-core";
import fixture from "../../../../fixtures/timetable-october-2026.simulation.json";
import ConnectedTimetablePage from "./ConnectedTimetablePage";
import { scheduleApi, type CurrentSchedule } from "../import/connectedApi";
import { useBrowserSession } from "../auth/useBrowserSession";
import { ApiError } from "../../shared/api/client";
vi.mock("../import/connectedApi",()=>({scheduleApi:{current:vi.fn()}}));
vi.mock("../auth/useBrowserSession",()=>({useBrowserSession:vi.fn()}));
let root:Root,host:HTMLDivElement;
const session={workspaceRef:"owner-A",csrfToken:"test",expiresAt:"2099-01-01T00:00:00Z"};
function auth(workspaceRef="owner-A") { vi.mocked(useBrowserSession).mockReturnValue({session:{...session,workspaceRef},setSession:vi.fn(),checking:false,needsLogin:false,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()}); }
function saved(workspaceRef="owner-A"):CurrentSchedule {return {workspaceRef,scheduleId:"test-id",revision:1,confirmedAt:"2026-10-07T00:00:00+08:00",timetable:structuredClone(fixture) as TimetableImport};}
async function render() {await act(async()=>root.render(<ConnectedTimetablePage/>));}
async function refresh() {await act(async()=>Array.from(host.querySelectorAll("button")).find(b=>b.textContent==="刷新课表")!.click());}
describe("connected timetable read-only states",()=>{
 beforeEach(()=>{vi.clearAllMocks();vi.stubEnv("VITE_IDENTITY_PILOT","true");vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);auth();host=document.createElement("div");document.body.append(host);root=createRoot(host);});
 afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();vi.unstubAllEnvs();});
 it("distinguishes loading from an empty or failed timetable",async()=>{
   let resolve!:(v:CurrentSchedule)=>void;vi.mocked(scheduleApi.current).mockReturnValue(new Promise(r=>resolve=r));await render();
   expect(host.textContent).toContain("正在读取本人课表");expect(host.textContent).not.toContain("还没有已确认");
   await act(async()=>resolve(saved()));expect(host.textContent).toContain("已读取本人课表");
   expect(host.textContent).not.toContain("查找空闲时间");
 });
 it("refresh failure clears old records and never falls back to mock data",async()=>{
   vi.mocked(scheduleApi.current).mockResolvedValue(saved());await render();
   vi.mocked(scheduleApi.current).mockRejectedValue(new ApiError({status:503,code:"DEPENDENCY_UNAVAILABLE",message:"Dependency failed",requestId:"request-503"}));await refresh();
   expect(host.textContent).toContain("课表暂时未能加载");expect(host.textContent).toContain("request-503");
   expect(host.querySelectorAll(".tt-course")).toHaveLength(0);expect(host.textContent).not.toContain("还没有已确认");
 });
 it("shows import entry for a missing timetable instead of an error",async()=>{
   vi.mocked(scheduleApi.current).mockRejectedValue(new ApiError({status:404,code:"NOT_FOUND",message:"No schedule",requestId:"request-404"}));await render();
   expect(host.textContent).toContain("还没有已确认的课表");expect(host.querySelector('a[href="/tools/import"]')).not.toBeNull();
 });
 it("ignores a late response after an account switch",async()=>{
   let resolve!:(v:CurrentSchedule)=>void;vi.mocked(scheduleApi.current).mockReturnValueOnce(new Promise(r=>resolve=r)).mockResolvedValueOnce(saved("owner-B"));
   await render();auth("owner-B");await render();await act(async()=>resolve({...saved(),revision:99}));
   expect(host.textContent).toContain("版本 1");expect(host.textContent).not.toContain("版本 99");
 });
 it("refuses a response belonging to a different account",async()=>{
   vi.mocked(scheduleApi.current).mockResolvedValue(saved("owner-B"));await render();
   expect(host.textContent).toContain("课表归属与当前账号不一致");expect(host.querySelectorAll(".tt-course")).toHaveLength(0);
 });
});
