import { useEffect, useMemo, useRef, useState } from "react";
import type { TermCalendar, TimetableImport } from "@campus/import-core";
import { compactWeeks, courseColor, currentTeachingWeek, entryTime, shanghaiDay, termContains, weekView, WEEKDAYS } from "./viewModel";
import type { CourseEntry } from "./viewModel";
import "./timetable.css";

export { currentTeachingWeek } from "./viewModel";
export interface TimetablePageProps { timetable?: TimetableImport | null; today?: Date }
type View = "week" | "day";

export default function TimetablePage({ timetable = null, today }: TimetablePageProps) {
  const term = timetable?.term ?? null;
  const now = today ?? new Date();
  const todayDay = shanghaiDay(now);
  const [week, setWeek] = useState(() => currentTeachingWeek(term, now));
  const [view, setView] = useState<View>(() => typeof window !== "undefined" && window.matchMedia?.("(max-width: 640px)").matches ? "day" : "week");
  const [selectedDay, setSelectedDay] = useState(() => (new Date(todayDay).getUTCDay() + 6) % 7);
  const [detail, setDetail] = useState<{ entry: CourseEntry; date: string } | null>(null);
  useEffect(() => { setWeek(currentTeachingWeek(term, today ?? new Date())); }, [term?.term_id, term?.week1_monday, term?.teaching_weeks, today?.getTime()]);
  useEffect(() => { setDetail(null); }, [week, timetable]);
  const days = useMemo(() => timetable ? weekView(timetable, week) : [], [timetable, week]);
  if (!timetable || !term) return <main className="timetable-page">
    <p className="tt-eyebrow">课程 · 每周一览</p><h1>我的课表</h1>
    <div className="tt-empty"><h2>还没有已确认的课表</h2><p>导入并核对后，课程会按教学周显示在这里。</p><a className="tt-link-button" href="/tools/import">前往导入与核对</a></div>
  </main>;
  const coverage = timetable.source.coverage;
  const limited = coverage.completeness !== "complete" || coverage.scope !== "term";
  const withinTerm = termContains(term, todayDay);
  const currentDay = days[selectedDay];
  const total = days.reduce((sum, d) => sum + d.entries.length, 0);
  // Widen only days with overlapping courses, instead of squeezing cards into unreadable strips.
  const columnWidths = days.map(day => 118 * Math.max(1, ...day.entries.map(entry => entry.lanes)));
  const status = { demo: "虚构演示校历", official_verified: "校历已核实", user_confirmed: "校历由你确认", needs_confirmation: "校历待核对" }[term.calendar_status];
  function backToToday() {
    setWeek(currentTeachingWeek(term, today ?? new Date()));
    setSelectedDay((new Date(todayDay).getUTCDay() + 6) % 7);
  }
  function openDay(index: number) { setSelectedDay(index); setView("day"); }
  return <main className="timetable-page">
    <header className="tt-heading"><div><p className="tt-eyebrow">课程 · 每周一览</p><h1>我的课表</h1><p className="tt-subtitle">{term.term_id} <span className="tt-tag">{status}</span></p></div>
      <a className="tt-link-button tt-secondary" href="/tools/import">导入与核对</a>
    </header>
    {timetable.dataset_kind === "demo" && <p className="tt-notice" role="note">当前为虚构课表，不是本人教务数据。</p>}
    {limited && <p className="tt-notice tt-warning" role="note">课表覆盖不完整{coverage.week_numbers.length ? `（已覆盖第 ${compactWeeks(coverage.week_numbers)} 周）` : ""}。未显示课程不代表该时段可安排，请先核对导入范围。</p>}
    {!withinTerm && <p className="tt-notice" role="note">今天不在这个学期内，当前展示邻近教学周；可切换查看其他周。</p>}
    <section className="tt-toolbar" aria-label="课表视图与教学周">
      <div className="tt-week-controls"><button aria-label="上一周" disabled={week <= 1} onClick={() => setWeek(w => w - 1)}>‹</button>
        <label className="tt-week-label"><span className="tt-sr-only">教学周</span><select aria-label="教学周" value={week} onChange={e => setWeek(Number(e.target.value))}>{Array.from({ length: term.teaching_weeks }, (_, i) => <option key={i} value={i + 1}>第 {i + 1} 周</option>)}</select></label>
        <button aria-label="下一周" disabled={week >= term.teaching_weeks} onClick={() => setWeek(w => w + 1)}>›</button>
        <button className="tt-today-button" onClick={backToToday}>{withinTerm ? "回到本周" : "邻近教学周"}</button>
      </div>
      <div className="tt-view-switch" aria-label="显示方式"><button aria-pressed={view === "week"} onClick={() => setView("week")}>周视图</button><button aria-pressed={view === "day"} onClick={() => setView("day")}>日视图</button></div>
    </section>
    <div className="tt-week-summary" aria-live="polite"><span>{days[0].date.split("-").join(".")} — {days[6].date.slice(5).replace("-", ".")}</span><span>本周显示 {total} 次上课 · 点课程看详情</span></div>
    {days.some(d => d.conflicts) && <p className="tt-notice tt-warning" role="note">部分课程时间重叠，全部课程均已保留显示，请核对原课表。</p>}
    {view === "week" ? <div className="tt-scroll" role="region" aria-label="整周课表，可左右滚动" tabIndex={0}>
      <div className="tt-grid" style={{ gridTemplateColumns: `82px ${columnWidths.map(width => `minmax(${width}px, 1fr)`).join(" ")}`, minWidth: 82 + columnWidths.reduce((sum, width) => sum + width, 0) }}>
        <div className="tt-grid-head tt-axis-head">节次 / 时间</div>
        {days.map((day, i) => <button className={`tt-grid-head ${day.date === todayDay ? "tt-is-today" : ""}`} key={day.date} onClick={() => openDay(i)} aria-label={`查看 ${day.date} 周${WEEKDAYS[i]} 日课表`}>
          <strong>周{WEEKDAYS[i]} {day.date === todayDay && <span className="tt-today-dot">今天</span>}</strong><span>{day.date.slice(5).replace("-", "/")}</span>{day.note && <small>{day.note}</small>}
        </button>)}
        <div className="tt-axis">{term.periods.map(p => <div className="tt-period-label" key={p.period}><strong>第 {p.period} 节</strong><span>{p.start}</span><span>{p.end}</span></div>)}</div>
        {days.map(day => <div className={`tt-day-column ${day.date === todayDay ? "tt-is-today" : ""}`} key={day.date} style={{ gridTemplateRows: `repeat(${term.periods.length}, var(--tt-row-height))` }}>
          {term.periods.map((p,i) => <div aria-hidden="true" className="tt-grid-cell" key={p.period} style={{ gridRow: i + 1, gridColumn: 1 }} />)}
          {day.cancelled && <span className="tt-cancelled">调休停课</span>}
          {day.entries.map(entry => <button key={entry.key} className={`tt-course ${entry.end - entry.start === 1 ? "tt-course-short" : ""} tt-color-${courseColor(entry.course.course_id)}`} style={{
            gridRow: `${entry.start + 1} / ${entry.end + 1}`, gridColumn: 1,
            width: `calc(${100 / entry.lanes}% - 8px)`, marginLeft: `calc(${100 * entry.lane / entry.lanes}% + 4px)`,
          }} aria-label={`${entry.course.title}，${day.date}，${entryTime(term, entry)}，查看详情`} onClick={() => setDetail({ entry, date: day.date })}>
            <strong>{entry.course.title}</strong><span>{entry.meeting.location ?? "地点待确认"}</span><small>{entryTime(term, entry)}</small>{entry.lanes > 1 && <small>课程重叠</small>}
          </button>)}
        </div>)}
      </div>
    </div> : <section className="tt-day-view" aria-label="日课表">
      <div className="tt-day-picker">{days.map((day,i) => <button key={day.date} aria-pressed={selectedDay === i} onClick={() => setSelectedDay(i)}><span>周{WEEKDAYS[i]}</span><strong>{day.date.slice(8)}</strong>{day.date === todayDay && <small>今天</small>}</button>)}</div>
      <div className="tt-day-title"><h2>{currentDay.date} · 周{WEEKDAYS[selectedDay]}</h2><span>{currentDay.entries.length} 次上课</span></div>
      {currentDay.note && <p className="tt-notice">{currentDay.note}</p>}
      <div className="tt-day-list">{currentDay.entries.map(entry => <button key={entry.key} className={`tt-day-course tt-color-${courseColor(entry.course.course_id)}`} onClick={() => setDetail({ entry, date: currentDay.date })} aria-label={`${entry.course.title}，查看详情`}>
        <span className="tt-day-time"><strong>{term.periods[entry.start].start}</strong><span>{term.periods[entry.end-1].end}</span></span>
        <span className="tt-day-course-content"><strong>{entry.course.title}</strong><span>{entry.meeting.location ?? "地点待确认"}</span><small>第 {entry.meeting.start_period}–{entry.meeting.end_period} 节{entry.lanes > 1 ? " · 课程重叠" : ""}</small></span><span aria-hidden="true">›</span>
      </button>)}</div>
      {!currentDay.entries.length && <div className="tt-empty"><h3>{currentDay.cancelled ? "今天调休停课" : "当天没有已导入的课程"}</h3><p>这里只显示课表，不代表没有其他安排。</p></div>}
    </section>}
    <footer className="tt-footer"><span>单双周、调休与停课均按已导入校历显示。</span><a href="/tools/calendar">查冲突与推荐时间，请前往待办日历 →</a></footer>
    {detail && <CourseDetails term={term} entry={detail.entry} date={detail.date} onClose={() => setDetail(null)} />}
  </main>;
}

function CourseDetails({ term, entry, date, onClose }: { term: TermCalendar; entry: CourseEntry; date: string; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => { document.body.style.overflow = overflow; if (previous?.isConnected) previous.focus(); };
  }, []);
  const course = entry.course;
  return <div className="tt-modal-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="tt-modal" role="dialog" aria-modal="true" aria-labelledby="tt-detail-title" ref={panel} onKeyDown={e => {
      if (e.key === "Escape") { e.stopPropagation(); onClose(); }
      if (e.key === "Tab") {
        const items = panel.current?.querySelectorAll<HTMLElement>('button, a[href], select, input, [tabindex="0"]');
        if (!items?.length) return;
        const first = items[0], last = items[items.length-1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }}>
      <div className="tt-modal-heading"><span className="tt-eyebrow">课程详情</span><button aria-label="关闭课程详情" onClick={onClose}>×</button></div>
      <h2 id="tt-detail-title">{course.title}</h2><p>{date} · {entryTime(term, entry)}</p>
      <dl className="tt-detail-grid"><div><dt>上课地点</dt><dd>{entry.meeting.location ?? "待确认"}</dd></div><div><dt>任课教师</dt><dd>{course.teacher_display ?? "待确认"}</dd></div>
        <div><dt>学分</dt><dd>{course.credits ?? "未提供"}</dd></div><div><dt>课程代码</dt><dd>{course.course_code ?? "未提供"}</dd></div>
      </dl><h3>这门课的上课安排</h3>
      <ul className="tt-meeting-list">{course.meetings.map(m => <li key={m.meeting_id}><strong>周{WEEKDAYS[m.weekday-1]} · 第 {m.start_period}–{m.end_period} 节</strong><span>第 {compactWeeks(m.weeks)} 周</span><span>{m.location ?? "地点待确认"}</span></li>)}</ul>
      <p className="tt-detail-note">课程信息有误？请在导入核对流程中调整，课表展示不会自动修改原记录。</p><a className="tt-link-button" href="/tools/import">前往导入与核对</a>
    </div>
  </div>;
}
