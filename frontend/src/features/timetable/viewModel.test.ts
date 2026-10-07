import { describe, expect, it } from "vitest";
import type { TimetableImport } from "@campus/import-core";
import fixture from "../../../../fixtures/timetable-october-2026.simulation.json";
import { compactWeeks, currentTeachingWeek, entryTime, layoutEntries, shanghaiDay, termContains, weekView } from "./viewModel";
const sample = () => structuredClone(fixture) as TimetableImport;
describe("timetable view model", () => {
  it("uses Shanghai days and bounds the current week to the selected term", () => {
    const term = sample().term;
    expect(shanghaiDay(new Date("2026-10-11T16:01:00Z"))).toBe("2026-10-12");
    expect(currentTeachingWeek(term, new Date("2026-10-11T16:01:00Z"))).toBe(2);
    expect(currentTeachingWeek(term, new Date("2026-09-01T00:00:00Z"))).toBe(1);
    expect(currentTeachingWeek(term, new Date("2026-12-01T00:00:00Z"))).toBe(4);
    expect(termContains(term, "2026-11-01")).toBe(true);
    expect(termContains(term, "2026-11-02")).toBe(false);
  });
  it("compacts ordinary, single/double and nonconsecutive weeks without changing input", () => {
    expect(compactWeeks([4,1,2,3,7,7])).toBe("1–4、7");
    expect(compactWeeks([1,3,5])).toBe("1–5 单周");
    expect(compactWeeks([2,4,6])).toBe("2–6 双周");
    expect(compactWeeks([])).toBe("");
  });
  it("renders one continuous card per meeting using the supplied period times", () => {
    const tt = sample();
    const wed = weekView(tt, 1)[2];
    expect(wed.entries).toHaveLength(2);
    expect(wed.entries[0]).toMatchObject({ start:0, end:2, lanes:1 });
    expect(entryTime(tt.term, wed.entries[0])).toBe("08:00–09:40");
    tt.term.periods[0].start = "08:10";
    expect(entryTime(tt.term, weekView(tt,1)[2].entries[0])).toBe("08:10–09:40");
  });
  it("applies replacement weeks and cancellation without guessing free time", () => {
    const tt=sample();
    tt.term.overrides = [
      { date:"2026-10-05", action:"replace", teaching_week:1, weekday:3, source_ref:"test"},
      { date:"2026-10-07", action:"cancel", teaching_week:null, weekday:null, source_ref:"test"},
    ];
    const days=weekView(tt,1);
    expect(days[0].entries).toHaveLength(2);
    expect(days[0].note).toContain("按第1周周三");
    expect(days[2].entries).toHaveLength(0);
    expect(days[2].cancelled).toBe(true);
  });
  it("keeps overlapping courses visible and lets adjacent courses reuse a lane", () => {
    const entry=weekView(sample(),1)[2].entries[0];
    const input=[{...entry,key:"a",start:0,end:3},{...entry,key:"b",start:1,end:2},{...entry,key:"c",start:2,end:4},{...entry,key:"d",start:4,end:5}];
    const laid=layoutEntries(input);
    expect(laid.map(e=>[e.key,e.lane,e.lanes])).toEqual([["a",0,2],["b",1,2],["c",1,2],["d",0,1]]);
    expect(input[0].lanes).toBe(1);
  });
  it("respects single-week coverage rather than repeating courses across every week", () => {
    const tt=sample();tt.courses[0].meetings[0].weeks=[1];
    expect(weekView(tt,2)[2].entries.map(e=>e.course.course_id)).not.toContain("simulation-MATH");
  });
});
