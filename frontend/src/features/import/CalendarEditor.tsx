import { useEffect, useState } from "react";
import { validateTermCalendarStructure, type TermCalendar } from "@campus/import-core";

// Reference times from the supplied Nankai timetable. They remain editable and
// are never called official-verified merely because they appear in this form.
const TIMES = "08:00-08:45\n08:55-09:40\n10:00-10:45\n10:55-11:40\n12:00-12:45\n12:55-13:40\n14:00-14:45\n14:55-15:40\n16:00-16:45\n16:55-17:40\n18:30-19:15\n19:25-20:10\n20:20-21:05\n21:15-22:00";
export default function CalendarEditor({ initial, termHint = "", onConfirm }: { initial?: TermCalendar | null; termHint?: string; onConfirm: (value: TermCalendar) => void }) {
 const [term,setTerm]=useState(initial?.term_id ?? termHint);
 useEffect(()=>{setTerm(value=>value || termHint);},[termHint]);
 const [monday,setMonday]=useState(initial?.week1_monday ?? "");
 const [weeks,setWeeks]=useState(initial?.teaching_weeks ?? 19);
 const [times,setTimes]=useState(initial?.periods.map(p=>`${p.start}-${p.end}`).join("\n") ?? TIMES);
 const [error,setError]=useState("");
 function confirm() {
  const periods=times.trim().split(/\n/).map((line,i)=>{const parts=line.trim().split("-");return {period:i+1,start:parts[0],end:parts[1]};});
  const value:TermCalendar={term_id:term,timezone:"Asia/Shanghai",week1_monday:monday,teaching_weeks:weeks,calendar_status:"user_confirmed",periods,
   overrides:initial?.overrides ?? [],source_ref:"本人在导入页核对校历与节次时间"};
  const validation=validateTermCalendarStructure(value);
  if(!validation.ok) {setError("请填写完整学期、日期及 HH:MM-HH:MM 格式的节次时间。");return;}
  if(new Date(`${monday}T00:00:00Z`).getUTCDay()!==1) {setError("第一教学周起始日必须是周一。");return;}
  if(periods.some((p,i)=>p.start>=p.end || (i>0 && p.start<periods[i-1].end))) {setError("每节起止时间必须递增且互不重叠。");return;}
  setError("");onConfirm(value);
 }
 return <section className="import-calendar"><h3>核对学期与上课时刻</h3><p>教务表格只有周次和节次；需先核对校历，才能显示正确日期。下面时刻是可修改的参考值，不是自动核实的官方校历。</p><p>不同学校或校区可逐节修改时间，也可增加或删除行。第1行对应第1节，依次排列；不会自动识别学校作息。学期、节次时间及调休将与本人课表一起保存。</p>
  <label>学期名称<input value={term} placeholder="例如 2026-2027学年1学期" onChange={e=>setTerm(e.target.value)}/></label>
  <label>第一教学周周一<input type="date" value={monday} onChange={e=>setMonday(e.target.value)}/></label>
  <label>学期教学周数<input type="number" min="1" max="60" value={weeks} onChange={e=>setWeeks(Number(e.target.value))}/></label>
  <label>每节课起止时间（每行一节）<textarea rows={14} value={times} onChange={e=>setTimes(e.target.value)}/></label>
  <p>学校临时调休若未提供，仍需另行核对；导入已有校历 JSON 时会保留其中调休。</p>
  <button type="button" onClick={confirm}>我已核对，使用这个校历</button>{error && <p role="alert">{error}</p>}
 </section>;
}
