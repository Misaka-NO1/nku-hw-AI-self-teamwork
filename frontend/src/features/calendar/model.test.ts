import { describe, expect, it } from "vitest";
import { calendarIcs, exactCandidates, isOverdue, monthDays, occursOn, plannedRange, previewTasks, reminderKey, remindersDue, shanghaiDay, shiftDay, shiftMonth, summary } from "./model";

describe("calendar dates and semantics",()=>{
  it("uses Shanghai dates across UTC midnight",()=>{
    expect(shanghaiDay("2026-10-05T16:30:00Z")).toBe("2026-10-06");
    expect(shiftDay("2026-12-31",1)).toBe("2027-01-01");
    expect(shiftMonth("2026-01",-1)).toBe("2025-12");
  });
  it("renders 42 Monday-first days including adjacent months",()=>{
    const days=monthDays("2026-10");
    expect(days.length).toBe(42);expect(days[0]).toBe("2026-09-28");expect(days[41]).toBe("2026-11-08");
    expect(new Set(days).size).toBe(42);
  });
  it("does not turn a deadline into scheduled work",()=>{
    const task=previewTasks("2026-10-06")[1];
    expect(plannedRange(task)).toBeNull();expect(occursOn(task,"2026-10-07")).toBe(true);
  });
  it("counts pending, overdue and unplanned independently",()=>{
    expect(summary(previewTasks("2026-10-06"),new Date("2026-10-06T12:00:00+08:00")))
      .toEqual({pending:3,today:1,overdue:1,unplanned:2});
  });
  it("date-only deadlines become overdue next day, without guessing 23:59",()=>{
    const task=previewTasks("2026-10-06")[1];task.notice.due={at:null,date:"2026-10-06",precision:"date"};
    expect(isOverdue(task,new Date("2026-10-06T23:59:00+08:00"))).toBe(false);
    expect(isOverdue(task,new Date("2026-10-07T00:00:00+08:00"))).toBe(true);
    task.status="completed";expect(isOverdue(task,new Date("2026-10-08T00:00:00Z"))).toBe(false);
  });
  it("end midnight belongs only to preceding day",()=>{
    const task=previewTasks("2026-10-06")[0];task.notice.due={at:null,date:null,precision:"unknown"};
    task.scheduledStart="2026-10-06T23:00:00+08:00";task.scheduledEnd="2026-10-07T00:00:00+08:00";
    expect(occursOn(task,"2026-10-06")).toBe(true);expect(occursOn(task,"2026-10-07")).toBe(false);
  });
  it("generates exact duration only within returned windows",()=>{
    const start="2026-10-06T18:00:00+08:00";
    const windows=[{start,end:"2026-10-06T19:00:00+08:00",durationMinutes:60},{start,end:"2026-10-06T18:10:00+08:00",durationMinutes:10}];
    expect(exactCandidates(windows,30)).toEqual([{start,end:"2026-10-06T10:30:00.000Z",durationMinutes:30}]);
    expect(exactCandidates(windows,null)).toEqual([]);expect(exactCandidates(windows,120)).toEqual([]);
  });
});
describe("calendar reminders and export",()=>{
  it("reminds only pending planned tasks, including zero-minute reminders",()=>{
    const task=previewTasks("2026-10-06")[0];task.reminderMinutes=0;
    expect(remindersDue([task],new Date("2026-10-06T15:59:00+08:00"))).toHaveLength(0);
    expect(remindersDue([task],new Date("2026-10-06T16:00:00+08:00"))).toHaveLength(1);
    expect(remindersDue([task],new Date("2026-10-06T16:30:00+08:00"))).toHaveLength(0);
    task.status="completed";expect(reminderKey(task)).toBeNull();
  });
  it("revision and reminder changes create distinct dedup keys",()=>{
    const task=previewTasks("2026-10-06")[0], key=reminderKey(task);
    task.calendarRevision++;expect(reminderKey(task)).not.toBe(key);
    task.reminderMinutes=null;expect(reminderKey(task)).toBeNull();
  });
  it("exports only pending actual arrangements with UTC alarms",()=>{
    const ics=calendarIcs(previewTasks("2026-10-06"),new Date("2026-10-06T00:00:00Z"));
    expect(ics.match(/BEGIN:VEVENT/g)).toHaveLength(1);expect(ics).toContain("DTSTART:20261006T080000Z");
    expect(ics).toContain("TRIGGER:-PT15M");expect(ics).not.toContain("准备小组展示");expect(ics.endsWith("\r\n")).toBe(true);
  });
  it("escapes text and folds UTF-8 without splitting codepoints",()=>{
    const task=previewTasks("2026-10-06")[0];task.notice.title="报告,材料;备注\\换行\n"+"中文".repeat(60);
    const ics=calendarIcs([task],new Date("2026-10-06T00:00:00Z"));
    expect(ics).toContain("报告\\,材料\\;备注\\\\换行\\n");
    for(const line of ics.split("\r\n"))expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
    expect(ics.replace(/\r\n /g,"")).toContain("中文".repeat(60));
  });
  it("empty export is a valid calendar with no invented event",()=>{
    expect(calendarIcs([],new Date("2026-10-06T00:00:00Z"))).not.toContain("BEGIN:VEVENT");
  });
});
