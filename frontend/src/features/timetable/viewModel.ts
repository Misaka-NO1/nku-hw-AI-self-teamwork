import { actualDateFor, getEffectiveTemplate } from "@campus/import-core";
import type { Course, Meeting, TermCalendar, TimetableImport } from "@campus/import-core";

export const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
export function shanghaiDay(now: Date): string {
  return new Date(now.getTime() + 8 * 3600000).toISOString().slice(0, 10);
}
/** B's 74ec7df current-week feature; stable across the device's timezones. */
export function currentTeachingWeek(term: TermCalendar | null, today: Date): number {
  if (!term || Number.isNaN(today.getTime())) return 1;
  const days = Math.floor((Date.parse(shanghaiDay(today)) - Date.parse(term.week1_monday)) / 86400000);
  return Number.isNaN(days) ? 1 : Math.min(Math.max(Math.floor(days / 7) + 1, 1), term.teaching_weeks);
}
export function termContains(term: TermCalendar, day: string): boolean {
  return day >= term.week1_monday && day <= actualDateFor(term, term.teaching_weeks, 7);
}
export function compactWeeks(input: number[]): string {
  const weeks = [...new Set(input)].sort((a, b) => a - b);
  if (weeks.length > 2 && weeks.every((w, i) => !i || w === weeks[i - 1] + 2)) {
    return `${weeks[0]}–${weeks[weeks.length - 1]}${weeks[0] % 2 ? " 单周" : " 双周"}`;
  }
  const parts: string[] = [];
  for (let i = 0; i < weeks.length; i += 1) {
    const first = weeks[i];
    while (i + 1 < weeks.length && weeks[i + 1] === weeks[i] + 1) i += 1;
    parts.push(first === weeks[i] ? String(first) : `${first}–${weeks[i]}`);
  }
  return parts.join("、");
}
export interface CourseEntry {
  key: string; course: Course; meeting: Meeting;
  /** zero-based start and exclusive end indices in term.periods (not minutes). */
  start: number; end: number; lane: number; lanes: number;
}
export interface DayView {
  weekday: number; date: string; note: string | null; cancelled: boolean;
  entries: CourseEntry[]; conflicts: boolean;
}

/** Group overlapping ranges, then put every course in a visible lane. */
export function layoutEntries(input: CourseEntry[]): CourseEntry[] {
  const sorted = input.map(item => ({ ...item })).sort((a,b) => a.start-b.start || a.end-b.end || a.key.localeCompare(b.key));
  let group: CourseEntry[] = []; let finish = -1;
  function assign() {
    const ends: number[] = [];
    for (const entry of group) {
      let lane = ends.findIndex(end => end <= entry.start);
      if (lane < 0) lane = ends.length;
      ends[lane] = entry.end; entry.lane = lane;
    }
    for (const entry of group) entry.lanes = ends.length;
    group = [];
  }
  for (const entry of sorted) {
    if (entry.start >= finish) { assign(); finish = entry.end; }
    else finish = Math.max(finish, entry.end);
    group.push(entry);
  }
  assign(); return sorted;
}
export function weekView(timetable: TimetableImport, week: number): DayView[] {
  const term = timetable.term;
  return WEEKDAYS.map((_, i) => {
    const date = actualDateFor(term, week, i + 1);
    const template = getEffectiveTemplate(term, date, week, i + 1);
    const entries: CourseEntry[] = [];
    if (template) for (const course of timetable.courses) for (const meeting of course.meetings) {
      if (meeting.weekday !== template.weekday || !meeting.weeks.includes(template.week)) continue;
      const start = term.periods.findIndex(p => p.period === meeting.start_period);
      const last = term.periods.findIndex(p => p.period === meeting.end_period);
      if (start < 0 || last < start) continue; // validated transport; never infer a missing time.
      entries.push({ key: `${date}:${course.course_id}:${meeting.meeting_id}`, course, meeting, start, end: last + 1, lane: 0, lanes: 1 });
    }
    const laidOut = layoutEntries(entries);
    return { weekday:i+1, date, cancelled:template===null,
      note:template===null ? "调休停课" : template.overridden ? `按第${template.week}周周${WEEKDAYS[template.weekday-1]}上课` : null,
      entries:laidOut, conflicts:laidOut.some(e=>e.lanes>1) };
  });
}
export function entryTime(term: TermCalendar, entry: CourseEntry): string {
  return `${term.periods[entry.start].start}–${term.periods[entry.end-1].end}`;
}
export function courseColor(id: string): number {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return Math.abs(hash) % 6;
}
