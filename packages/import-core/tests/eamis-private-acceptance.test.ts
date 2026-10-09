// @vitest-environment jsdom
// Optional owner-authorized local snapshot. No real data is checked into Git.
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { parseImportFile } from "../src/parse";
import type { TermCalendar } from "../src/types";
it.runIf(!!process.env.EAMIS_PRIVATE_FILE)("parses the authorized live course grid without replacing it with fixtures", () => {
 const times="08:00-08:45,08:55-09:40,10:00-10:45,10:55-11:40,12:00-12:45,12:55-13:40,14:00-14:45,14:55-15:40,16:00-16:45,16:55-17:40,18:30-19:15,19:25-20:10,20:20-21:05,21:15-22:00";
 const calendar:TermCalendar={term_id:"2026-2027学年1学期",timezone:"Asia/Shanghai",week1_monday:"2026-09-07",teaching_weeks:19,calendar_status:"user_confirmed",overrides:[],source_ref:"校历换算待本人最终核对；本测试只核对原始星期、节次与周次",periods:times.split(",").map((time,i)=>({period:i+1,start:time.split("-")[0],end:time.split("-")[1]}))};
 const result=parseImportFile({name:"authorized-live.html",content:readFileSync(process.env.EAMIS_PRIVATE_FILE!,"utf8")},"html",calendar,{datasetKind:"personal"});
 expect(result.issues.filter(i=>i.blocking)).toEqual([]);expect(result.payload).not.toBeNull();
 const courses=result.payload!.courses;
 expect(new Set(courses.map(c=>c.course_id)).size).toBe(10);
 // Keep this optional public test structural: never publish the owner's
 // actual course names or per-course weekday/period arrangement.
 expect(courses.every(c=>c.meetings.length>0)).toBe(true);
 expect(courses.flatMap(c=>c.meetings).every(m=>m.weekday>=1&&m.weekday<=7&&m.start_period<=m.end_period)).toBe(true);
 expect(result.payload!.source.coverage.completeness).toBe("complete");
 expect(result.payload!.source.coverage.scope).toBe("term");
 expect(result.payload!.source.coverage.week_numbers).toEqual(Array.from({length:19},(_,i)=>i+1));
 expect(courses.every(c=>c.course_code===null)).toBe(true);
});
