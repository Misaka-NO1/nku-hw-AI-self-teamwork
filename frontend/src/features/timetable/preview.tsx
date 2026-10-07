/** Development-only UI harness: no API calls, auth, saved records or production routes. */
import { useState } from "react";
import { createRoot } from "react-dom/client";
import type { TimetableImport } from "@campus/import-core";
import fixture from "../../../../fixtures/timetable-october-2026.simulation.json";
import TimetablePage from "./TimetablePage";
import "../../shared/styles.css";

function example(): TimetableImport {
  const tt = structuredClone(fixture) as TimetableImport;
  tt.term.periods = [
    ["08:00","08:45"],["08:55","09:40"],["10:00","10:45"],["10:55","11:40"],
    ["12:00","12:45"],["12:55","13:40"],["14:00","14:45"],["14:55","15:40"],
    ["16:00","16:45"],["16:55","17:40"],["18:30","19:15"],["19:25","20:10"],
    ["20:20","21:05"],["21:15","22:00"],
  ].map(([start,end],i)=>({period:i+1,start,end}));
  tt.courses[0].meetings.push({...tt.courses[0].meetings[0],meeting_id:"preview-math-mon",weekday:1,start_period:3,end_period:4});
  tt.courses[1].meetings[0].start_period=7;tt.courses[1].meetings[0].end_period=10;
  tt.courses[2].meetings[0].start_period=11;tt.courses[2].meetings[0].end_period=12;
  tt.courses[3].meetings[0].start_period=1;tt.courses[3].meetings[0].end_period=2;
  return tt;
}
function Preview() {
  const [scenario,setScenario]=useState("normal");
  const tt=example();
  if(scenario==="overlap") tt.courses.push({...tt.courses[0],course_id:"preview-overlap",title:"重叠课程（虚构测试）",
    meetings:[{...tt.courses[0].meetings[0],meeting_id:"preview-overlap-m",start_period:2,end_period:3}]});
  if(scenario==="partial") {
    tt.source.coverage={scope:"selected_weeks",completeness:"partial",week_numbers:[1]};
    tt.courses.forEach(c=>c.meetings.forEach(m=>m.weeks=[1]));
  }
  if(scenario==="overrides") tt.term.overrides=[
    {date:"2026-10-05",action:"replace",teaching_week:1,weekday:3,source_ref:"UI preview only"},
    {date:"2026-10-07",action:"cancel",teaching_week:null,weekday:null,source_ref:"UI preview only"},
  ];
  return <div className="app-shell">
    <header className="app-header"><strong>南开校园助手 · 课表 UI 预览</strong></header>
    <p className="tt-notice">仅本地 UI 验证 · 虚构测试课程 · 不读取账号、不保存、不上传。</p>
    <label>展示场景 <select aria-label="展示场景" value={scenario} onChange={e=>setScenario(e.target.value)}>
      <option value="normal">普通课表（14 节）</option><option value="overlap">重叠课程</option><option value="partial">仅导入部分周</option><option value="overrides">调休与停课</option>
    </select></label>
    <TimetablePage timetable={tt} today={new Date("2026-10-07T04:00:00Z")} />
  </div>;
}
const host=document.getElementById("root")!;
if(import.meta.env.DEV) createRoot(host).render(<Preview />);
else host.textContent="课表 UI 预览仅在本地开发环境可用。";
