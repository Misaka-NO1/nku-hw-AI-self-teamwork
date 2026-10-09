// @vitest-environment jsdom
// Optional local owner-authorized file; course contents never enter Git or logs.
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { parseImportFile } from "../src/parse";
import type { TermCalendar } from "../src/types";
it.runIf(!!process.env.EAMIS_PRIVATE_JSON)("parses the supplied EAMS JSON with a locally reviewed calendar",()=>{
 const times="08:00-08:45,08:55-09:40,10:00-10:45,10:55-11:40,12:00-12:45,12:55-13:40,14:00-14:45,14:55-15:40,16:00-16:45,16:55-17:40,18:30-19:15,19:25-20:10,20:20-21:05,21:15-22:00";
 const calendar:TermCalendar={term_id:"2026-2027学年1学期",timezone:"Asia/Shanghai",week1_monday:"2026-09-07",teaching_weeks:19,calendar_status:"user_confirmed",overrides:[],source_ref:"仅本地解析验收，不是本人保存确认",periods:times.split(",").map((s,i)=>({period:i+1,start:s.split("-")[0],end:s.split("-")[1]}))};
 const result=parseImportFile({name:"timetable-import.json",content:readFileSync(process.env.EAMIS_PRIVATE_JSON!,"utf8")},"json",calendar,{datasetKind:"personal"});
 expect(result.issues.filter(i=>i.blocking)).toEqual([]);expect(result.payload?.dataset_kind).toBe("personal");
 expect(result.payload?.courses).toHaveLength(10);expect(result.payload?.source.coverage).toEqual({scope:"term",week_numbers:Array.from({length:19},(_,i)=>i+1),completeness:"complete"});
 expect(result.payload?.courses.flatMap(c=>c.meetings).filter(m=>m.weeks.includes(5))).toHaveLength(15);
});
