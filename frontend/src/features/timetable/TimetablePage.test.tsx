// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TimetableImport } from "@campus/import-core";
import fixture from "../../../../fixtures/timetable-october-2026.simulation.json";
import TimetablePage from "./TimetablePage";
let root:Root, host:HTMLDivElement;
const today=new Date("2026-10-07T04:00:00Z");
const sample=()=>structuredClone(fixture) as TimetableImport;
function button(label:string) {
  const b=Array.from(host.querySelectorAll("button")).find(el=>el.textContent===label || el.getAttribute("aria-label")===label);
  if(!b) throw new Error("No button "+label);return b;
}
async function mount(timetable:TimetableImport|null=sample()) { await act(async()=>{root.render(<TimetablePage timetable={timetable} today={today}/>);}); }
async function click(el:HTMLElement) { await act(async()=>el.click()); }
describe("timetable interactions",()=>{
  beforeEach(()=>{vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);host=document.createElement("div");document.body.append(host);root=createRoot(host);});
  afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();vi.restoreAllMocks();});
  it("shows continuous cards and opens details with keyboard focus restored on Escape",async()=>{
    await mount();
    expect(host.querySelectorAll(".tt-course")).toHaveLength(4);
    const card=host.querySelector<HTMLButtonElement>(".tt-course")!;
    expect(card.style.gridRow).toBe("1 / 3");
    card.focus();await click(card);
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain("上课地点");
    expect(document.activeElement?.getAttribute("aria-label")).toBe("关闭课程详情");
    await act(async()=>document.activeElement!.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true})));
    expect(host.querySelector('[role="dialog"]')).toBeNull();expect(document.activeElement).toBe(card);
    expect(document.body.style.overflow).toBe("");
  });
  it("navigates weeks and resets to the current teaching week",async()=>{
    await mount();expect(button("上一周").disabled).toBe(true);
    await click(button("下一周"));expect(host.querySelector("select")?.value).toBe("2");
    await click(button("回到本周"));expect(host.querySelector("select")?.value).toBe("1");
  });
  it("handles async loading of the timetable and a new term without retaining the old week",async()=>{
    await mount(null);expect(host.textContent).toContain("还没有已确认");
    await mount();expect(host.querySelector("select")?.value).toBe("1");
    const tt=sample();tt.term.week1_monday="2026-09-28";await mount(tt);
    expect(host.querySelector("select")?.value).toBe("2");
  });
  it("defaults to daily mode on small screens; empty days do not claim availability",async()=>{
    vi.spyOn(window,"matchMedia").mockReturnValue({matches:true} as MediaQueryList);
    await mount();expect(host.querySelector(".tt-day-view")).not.toBeNull();
    const dayButtons=host.querySelectorAll<HTMLButtonElement>(".tt-day-picker button");
    await click(dayButtons[0]);expect(host.textContent).toContain("当天没有已导入的课程");
    expect(host.textContent).toContain("不代表没有其他安排");
    expect(host.querySelector(".tt-scroll")).toBeNull();
  });
  it("shows every overlapping course and partial coverage warnings",async()=>{
    const tt=sample();tt.courses.push({...tt.courses[0],course_id:"overlap",title:"重叠课程",meetings:[{...tt.courses[0].meetings[0],meeting_id:"overlap-m"}]});
    tt.source.coverage={scope:"selected_weeks",week_numbers:[1],completeness:"partial"};
    await mount(tt);expect(host.querySelectorAll(".tt-course")).toHaveLength(5);
    expect(host.textContent).toContain("部分课程时间重叠");
    expect(host.textContent).toContain("课表覆盖不完整");
    expect(host.querySelector<HTMLElement>(".tt-grid")!.style.minWidth).toBe("1026px");
    const cards=Array.from(host.querySelectorAll<HTMLButtonElement>(".tt-course")).filter(b=>b.style.gridRow==="1 / 3");
    expect(cards.every(c=>c.style.width.includes("50%"))).toBe(true);
  });
  it("renders course titles as text, not executable markup",async()=>{
    const tt=sample();tt.courses[0].title="<img src=x onerror=alert(1)>";
    await mount(tt);expect(host.querySelector(".tt-course img")).toBeNull();
    expect(host.textContent).toContain("<img src=x onerror=alert(1)>");
  });
});
