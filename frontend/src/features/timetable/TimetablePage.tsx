import { useMemo, useState } from "react";

import { actualDateFor, getEffectiveTemplate } from "@campus/import-core";
import type { Course, Meeting, TermCalendar, TimetableImport } from "@campus/import-core";

/**
 * TimetablePage（/tools/timetable，owner: B；路由接入由 C 负责）。
 *
 * 周课表：选择教学周，按 星期 × 节次 网格展示课程卡片。
 * - 同一格可显示多门课程，不互相覆盖；
 * - 跨多节的课程在每个所占节次都出现；
 * - 调休/停课 override 应用到选中周：cancel 显示停课，replace 显示替换模板课程；
 * - 保留 coverage 提示——课表不完整时不宣称“全天有空”。
 */

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];
const COURSE_COLORS = ["#dbeafe", "#dcfce7", "#fef9c3", "#fee2e2", "#ede9fe", "#ffedd5"];

export interface TimetablePageProps {
  timetable: TimetableImport | null;
}

interface CellEntry {
  course: Course;
  meeting: Meeting;
}

interface DayView {
  /** null 表示当日因调休 cancel 无课程 */
  template: { week: number; weekday: number } | null;
  overridden: boolean;
  overrideNote: string | null;
}

export default function TimetablePage({ timetable }: TimetablePageProps) {
  const term: TermCalendar | null = timetable?.term ?? null;
  const [week, setWeek] = useState(1);

  // 每个星期的实际模板（应用调休/停课后）
  const dayViews = useMemo<DayView[]>(() => {
    if (!term) return [];
    return WEEKDAY_LABELS.map((_, index) => {
      const weekday = index + 1;
      const actualDate = actualDateFor(term, week, weekday);
      const template = getEffectiveTemplate(term, actualDate, week, weekday);
      if (template === null) {
        return { template: null, overridden: true, overrideNote: "调休/停课" };
      }
      return {
        template: { week: template.week, weekday: template.weekday },
        overridden: template.overridden,
        overrideNote: template.overridden
          ? `按第${template.week}周周${WEEKDAY_LABELS[template.weekday - 1]}上课`
          : null,
      };
    });
  }, [term, week]);

  // key: `${列星期}-${节次}` → 该格全部课程（不覆盖、跨节填充）
  const cells = useMemo(() => {
    const grid = new Map<string, CellEntry[]>();
    if (!timetable) return grid;
    dayViews.forEach((day, columnIndex) => {
      if (day.template === null) return;
      const column = columnIndex + 1;
      for (const course of timetable.courses) {
        for (const meeting of course.meetings) {
          if (meeting.weekday !== day.template.weekday) continue;
          if (!meeting.weeks.includes(day.template.week)) continue;
          for (let period = meeting.start_period; period <= meeting.end_period; period += 1) {
            const key = `${column}-${period}`;
            const list = grid.get(key) ?? [];
            list.push({ course, meeting });
            grid.set(key, list);
          }
        }
      }
    });
    return grid;
  }, [timetable, dayViews]);

  if (!timetable || !term) {
    return (
      <main>
        <h1>我的课表</h1>
        <p>还没有已确认的课表。请先打开“导入”页导入并核对。</p>
      </main>
    );
  }

  const coverage = timetable.source.coverage;
  const coverageWarning = coverage.completeness !== "complete" || coverage.scope !== "term";

  return (
    <main>
      <h1>我的课表</h1>
      <p>
        学期：{term.term_id}（校历状态：{term.calendar_status}）
      </p>
      {coverageWarning && (
        <p role="note">
          课表覆盖范围有限：{coverage.scope}（{coverage.completeness}，周次{" "}
          {coverage.week_numbers.join(",")}）。空档/冲突结果只基于已导入课程。
        </p>
      )}

      <label>
        教学周：
        <select value={week} onChange={(event) => setWeek(Number(event.target.value))}>
          {Array.from({ length: term.teaching_weeks }, (_, index) => index + 1).map((w) => (
            <option key={w} value={w}>
              第 {w} 周
            </option>
          ))}
        </select>
      </label>

      <table>
        <thead>
          <tr>
            <th>节次</th>
            {WEEKDAY_LABELS.map((label, index) => (
              <th key={label}>
                周{label}
                {dayViews[index]?.overrideNote && (
                  <>
                    <br />
                    <em>{dayViews[index].overrideNote}</em>
                  </>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {term.periods.map((period) => (
            <tr key={period.period}>
              <th>
                第{period.period}节
                <br />
                {period.start}-{period.end}
              </th>
              {WEEKDAY_LABELS.map((_, weekdayIndex) => {
                const entries = cells.get(`${weekdayIndex + 1}-${period.period}`) ?? [];
                if (entries.length === 0) {
                  return <td key={weekdayIndex} />;
                }
                return (
                  <td key={weekdayIndex}>
                    {entries.map(({ course, meeting }) => (
                      <div
                        key={`${course.course_id}-${meeting.meeting_id}`}
                        style={{
                          backgroundColor:
                            COURSE_COLORS[Math.abs(hashCode(course.course_id)) % COURSE_COLORS.length],
                          marginBottom: 4,
                          padding: 4,
                          borderRadius: 4,
                        }}
                      >
                        <strong>{course.title}</strong>
                        <br />
                        {meeting.location ?? "地点待确认"}
                        <br />
                        周次：{meeting.weeks.join(",")}
                        {term.calendar_status !== "official_verified" && (
                          <>
                            <br />
                            <em>待确认</em>
                          </>
                        )}
                      </div>
                    ))}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

function hashCode(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash;
}
