import type { TaskRecord } from "../tasks/api";

export type TaskStatus = "pending" | "completed" | "cancelled";
export interface CalendarTask extends TaskRecord {
  calendarRevision: number;
  status: TaskStatus;
  scheduledStart: string | null;
  scheduledEnd: string | null;
  reminderMinutes: number | null;
}
export interface Candidate { start: string; end: string; durationMinutes: number }
export interface CalendarData {
  items: CalendarTask[];
  capabilities: { scheduling: boolean; status: boolean; reminders: boolean };
  legacy?: boolean;
}
export const READ_ONLY = { scheduling:false, status:false, reminders:false };
export function shanghaiDay(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(date);
  const part = (type:string) => parts.find(p=>p.type===type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}
export function shiftDay(day:string, delta:number):string {
  const date = new Date(day + "T12:00:00+08:00");
  date.setTime(date.getTime() + delta * 86400000);
  return shanghaiDay(date);
}
export function monthDays(month:string):string[] {
  const first = month + "-01";
  // At Shanghai noon the UTC and local weekday agree, regardless of host timezone.
  const localWeekday = new Date(first + "T12:00:00+08:00").getUTCDay();
  const offset = (localWeekday + 6) % 7;
  return Array.from({length:42},(_,i)=>shiftDay(first,i-offset));
}
export function shiftMonth(month:string,delta:number):string {
  const [year, number] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year, number-1+delta,1,4));
  return shanghaiDay(date).slice(0,7);
}
export function plannedRange(task:CalendarTask):{start:string;end:string}|null {
  const start = task.scheduledStart ?? task.notice.event.start;
  const end = task.scheduledEnd ?? task.notice.event.end;
  return start && end && Date.parse(end)>Date.parse(start) ? {start,end} : null;
}
export function dueDay(task:CalendarTask):string {
  return task.notice.due.at ? shanghaiDay(task.notice.due.at) : task.notice.due.date ?? "";
}
export function occursOn(task:CalendarTask,day:string):boolean {
  const range = plannedRange(task);
  return !!range && shanghaiDay(range.start)<=day && shanghaiDay(new Date(Date.parse(range.end)-1))>=day || dueDay(task)===day;
}
export function isOverdue(task:CalendarTask,now:Date):boolean {
  if(task.status!=="pending") return false;
  return task.notice.due.at ? Date.parse(task.notice.due.at)<now.getTime()
    : !!task.notice.due.date && task.notice.due.date<shanghaiDay(now);
}
export function summary(tasks:CalendarTask[],now:Date) {
  const pending = tasks.filter(t=>t.status==="pending");
  return {pending:pending.length,today:pending.filter(t=>occursOn(t,shanghaiDay(now))).length,
    overdue:pending.filter(t=>isOverdue(t,now)).length,unplanned:pending.filter(t=>!plannedRange(t)).length};
}
export function formatTime(value:string|null):string {
  if(!value) return "未确定";
  return new Intl.DateTimeFormat("zh-CN",{timeZone:"Asia/Shanghai",month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(value));
}
export function exactCandidates(windows:Candidate[],minutes:number|null):Candidate[] {
  if(!minutes || minutes<=0) return [];
  return windows.filter(w=>Date.parse(w.end)-Date.parse(w.start)>=minutes*60000).map(w=>({
    start:w.start,end:new Date(Date.parse(w.start)+minutes*60000).toISOString(),durationMinutes:minutes,
  })).filter((w,i,all)=>all.findIndex(x=>Date.parse(x.start)===Date.parse(w.start))===i);
}
export function reminderKey(task:CalendarTask):string|null {
  const start=plannedRange(task)?.start;
  return task.status==="pending" && start && task.reminderMinutes!==null
    ? `${task.taskId}:${task.calendarRevision}:${start}:${task.reminderMinutes}` : null;
}
export function remindersDue(tasks:CalendarTask[],now:Date):CalendarTask[] {
  return tasks.filter(t=>{
    const range=plannedRange(t);
    return reminderKey(t)!==null && !!range && now.getTime()>=Date.parse(range.start)-t.reminderMinutes!*60000
      && now.getTime()<Date.parse(range.end);
  });
}
const escapeIcs=(text:string)=>text.replace(/\\/g,"\\\\").replace(/\r?\n/g,"\\n").replace(/;/g,"\\;").replace(/,/g,"\\,");
const utc=(value:string)=>new Date(value).toISOString().replace(/[-:]/g,"").replace(/\.\d{3}Z$/,"Z");
function fold(line:string):string {
  let output="", width=0;
  for(const char of line) {
    const bytes=new TextEncoder().encode(char).length;
    if(width+bytes>75) {output+="\r\n ";width=1;}
    output+=char;width+=bytes;
  }
  return output;
}
/** Only actual arrangements become events. A deadline alone is NOT a busy event. */
export function calendarIcs(tasks:CalendarTask[],now:Date):string {
  const lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//NKU Campus Assistant//Calendar//ZH","CALSCALE:GREGORIAN"];
  for(const task of tasks.filter(t=>t.status==="pending" && plannedRange(t))) {
    const range=plannedRange(task)!;
    lines.push("BEGIN:VEVENT",`UID:${escapeIcs(task.taskId)}@nku-campus-assistant`, `DTSTAMP:${utc(now.toISOString())}`,
      `SEQUENCE:${task.calendarRevision}`,`DTSTART:${utc(range.start)}`,`DTEND:${utc(range.end)}`,
      `SUMMARY:${escapeIcs(task.notice.title)}`,`DESCRIPTION:${escapeIcs("截止："+(task.notice.due.at??task.notice.due.date??"无")+"；以平台最新记录为准，导入后不会自动同步。")}`);
    if(task.reminderMinutes!==null) lines.push("BEGIN:VALARM","ACTION:DISPLAY",`TRIGGER:-PT${task.reminderMinutes}M`,`DESCRIPTION:${escapeIcs(task.notice.title)}`,"END:VALARM");
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n")+"\r\n";
}

/** Opt-in, memory-only UI fixture. Never replaces failed live requests. */
export function previewTasks(today:string):CalendarTask[] {
  const make=(id:string,title:string,day:string,start:string|null,due:string|null):CalendarTask=>({
    taskId:id, revision:1,calendarRevision:0,status:"pending",confirmedAt:today+"T08:00:00+08:00",
    scheduledStart:start?day+`T${start}:00+08:00`:null,
    scheduledEnd:start?new Date(Date.parse(day+`T${start}:00+08:00`)+1800000).toISOString():null,reminderMinutes:15,
    notice:{title,event:{start:null,end:null,date:null,precision:"unknown"},due:{at:due?day+`T${due}:00+08:00`:null,date:null,precision:due?"datetime":"unknown"},
      estimatedMinutes:30,earliestStart:null,materials:["演示材料"],sourceSpans:[],needsConfirmation:[]},
  });
  return [make("preview-1","提交课程报告",today,"16:00","20:00"),
    make("preview-2","准备小组展示",shiftDay(today,1),null,"18:00"),
    make("preview-3","核对报名材料",shiftDay(today,-1),null,"18:00"),
    {...make("preview-4","完成本周阅读",today,"10:00",null),status:"completed"}];
}
