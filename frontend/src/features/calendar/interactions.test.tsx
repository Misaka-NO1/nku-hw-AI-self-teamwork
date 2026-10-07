// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CalendarPage from "./CalendarPage";
import { loadCalendar, loadCandidates, updateCalendar } from "./api";
import { useBrowserSession } from "../auth/useBrowserSession";
import { previewTasks, shanghaiDay, type CalendarData } from "./model";
import { ApiError } from "../../shared/api/client";
vi.mock("./api",()=>({loadCalendar:vi.fn(),loadCandidates:vi.fn(),updateCalendar:vi.fn()}));
vi.mock("../auth/useBrowserSession",()=>({useBrowserSession:vi.fn()}));
let root:Root;
let container:HTMLDivElement;
let data:CalendarData;
const session={workspaceRef:"fictional-test-workspace",csrfToken:"fictional-csrf",expiresAt:"2099-01-01T00:00:00Z"};
function button(text:string):HTMLButtonElement {
  const result=Array.from(container.querySelectorAll("button")).find(b=>b.textContent===text);
  if(!result)throw new Error(`Missing button: ${text}`);return result;
}
async function click(element:HTMLElement) {await act(async()=>{element.click();});}
async function selectCandidate() {
  await click(container.querySelector(".calendar-task-card") as HTMLElement);
  await click(button("根据课表重新查候选"));
  await click(container.querySelector("input[type=radio]") as HTMLElement);
}
describe("calendar real-mode interactions with mocked D transport",()=>{
  beforeEach(async()=>{
    vi.clearAllMocks();vi.stubEnv("VITE_IDENTITY_PILOT","true");
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);vi.stubGlobal("crypto",{randomUUID:()=>"calendar-test-id"});
    data={items:previewTasks(shanghaiDay(new Date())),capabilities:{scheduling:true,status:true,reminders:true}};
    vi.mocked(useBrowserSession).mockReturnValue({session,setSession:vi.fn(),checking:false,needsLogin:false,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});
    vi.mocked(loadCalendar).mockResolvedValue(data);
    const day=shanghaiDay(new Date());
    vi.mocked(loadCandidates).mockResolvedValue({candidateSlots:[{start:day+"T18:00:00+08:00",end:day+"T19:00:00+08:00",durationMinutes:60}],needsConfirmation:[],coverage:{completeness:"unknown"}});
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root.render(createElement(CalendarPage));});
  });
  afterEach(async()=>{await act(async()=>root.unmount());container.remove();vi.unstubAllEnvs();vi.unstubAllGlobals();});
  it("mount and candidate selection never write; confirmation gates save",async()=>{
    expect(updateCalendar).not.toHaveBeenCalled();await selectCandidate();
    expect(button("确认保存安排 / 提醒").disabled).toBe(true);expect(updateCalendar).not.toHaveBeenCalled();
    await click(container.querySelector(".calendar-confirm input") as HTMLElement);
    expect(button("确认保存安排 / 提醒").disabled).toBe(false);
  });
  it("a lost response retries the exact same time and idempotency key",async()=>{
    await selectCandidate();await click(container.querySelector(".calendar-confirm input") as HTMLElement);
    vi.mocked(updateCalendar).mockRejectedValueOnce(new ApiError({status:503,code:"DEPENDENCY_UNAVAILABLE",message:"Response lost",requestId:"test-lost"}));
    await click(button("确认保存安排 / 提醒"));
    expect(container.textContent).toContain("Response lost");expect(button("确认保存安排 / 提醒").disabled).toBe(false);
    const original=vi.mocked(updateCalendar).mock.calls[0];
    const update=original[2];const updated={...data.items[0],calendarRevision:1,scheduledStart:update.scheduled_start,scheduledEnd:update.scheduled_end};
    vi.mocked(updateCalendar).mockResolvedValueOnce(updated);
    vi.mocked(loadCalendar).mockResolvedValueOnce({...data,items:[updated,...data.items.slice(1)]});
    await click(button("确认保存安排 / 提醒"));
    expect(vi.mocked(updateCalendar).mock.calls[1]).toEqual(original);
    expect(container.textContent).toContain("安排已保存并从后端读回");
  });
  it("write success without consistent readback does not show saved success",async()=>{
    await selectCandidate();await click(container.querySelector(".calendar-confirm input") as HTMLElement);
    vi.mocked(updateCalendar).mockResolvedValueOnce(data.items[0]);
    await click(button("确认保存安排 / 提醒"));
    expect(container.textContent).toContain("写入后读回不一致");expect(container.textContent).not.toContain("安排已保存并从后端读回");
  });
  it("legacy read-only records never enable write controls",async()=>{
    vi.mocked(loadCalendar).mockResolvedValueOnce({...data,legacy:true,capabilities:{scheduling:false,status:false,reminders:false}});
    await click(button("刷新记录"));await click(container.querySelector(".calendar-task-card") as HTMLElement);
    expect(button("标记完成").disabled).toBe(true);expect(button("根据课表重新查候选").disabled).toBe(true);
    expect(button("确认保存安排 / 提醒").disabled).toBe(true);expect(updateCalendar).not.toHaveBeenCalled();
  });
  it("expired timetable candidate rejection explains coverage without deleting tasks or writing",async()=>{
    await click(container.querySelector(".calendar-task-card") as HTMLElement);
    vi.mocked(loadCandidates).mockRejectedValueOnce(new ApiError({status:422,code:"VALIDATION_ERROR",message:"timetable_outside_term",requestId:"expired-term"}));
    await click(button("根据课表重新查候选"));
    expect(container.textContent).toContain("课表有效期已结束");
    expect(container.textContent).toContain("expired-term");
    expect(container.querySelectorAll(".calendar-task-card").length).toBeGreaterThan(0);
    expect(container.querySelector("input[type=radio]")).toBeNull();
    expect(updateCalendar).not.toHaveBeenCalled();
  });
  it("confirmation reason expiry cannot become an empty-slots success or enable selection",async()=>{
    await click(container.querySelector(".calendar-task-card") as HTMLElement);
    vi.mocked(loadCandidates).mockResolvedValueOnce({candidateSlots:[],needsConfirmation:["timetable_outside_term"],coverage:{completeness:"unknown"}});
    await click(button("根据课表重新查候选"));
    expect(container.textContent).toContain("课表有效期已结束");
    expect(container.textContent).not.toContain("本次未取得足够的连续空档");
    expect(container.querySelector("input[type=radio]")).toBeNull();
    expect(updateCalendar).not.toHaveBeenCalled();
  });
});
