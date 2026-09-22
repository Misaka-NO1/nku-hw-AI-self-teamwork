import { useMemo, useState } from "react";

import type { TermCalendar, TimetableImport } from "@campus/import-core";

/**
 * TimetablePage（/tools/timetable，owner: B；路由接入由 C 负责）。
 *
 * 周课表：选择教学周，按 星期 × 节次 网格展示课程卡片（课程/地点/周次），
 * 并保留 coverage 提示——课表不完整时不宣称“全天有空”。
 * 与“我的日程”共享同一 TermCalendar 规则；未确认条目明确标记。
 */

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];
const COURSE_COLORS = ["#dbeafe", "#dcfce7", "#fef9c3", "#fee2e2", "#ede9fe", "#ffedd5"];

export interface TimetablePageProps {
  timetable: TimetableImport | null;
}

interface Cell {
  courseTitle: string;
  location: string | null;
  weeks: number[];
  startPeriod: number;
  endPeriod: number;
}

export default function TimetablePage({ timetable }: TimetablePageProps) {
  const term: TermCalendar | null = timetable?.term ?? null;
  const [week, setWeek] = useState(1);

  const cells = useMemo(() => {
    const grid = new Map<string, Cell>();
    if (!timetable) return grid;
    timetable.courses.forEach((course, courseIndex) => {
      for (const meeting of course.meetings) {
        if (!meeting.weeks.includes(week)) continue;
        grid.set(`${meeting.weekday}-${meeting.start_period}`, {
          courseTitle: course.title,
          location: meeting.location,
          weeks: meeting.weeks,
          startPeriod: meeting.start_period,
          endPeriod: meeting.end_period,
        });
        void courseIndex;
      }
    });
    return grid;
  }, [timetable, week]);

  if (!timetable || !term) {
    return (
      <main>
        <h1>我的课表</h1>
        <p>还没有已确认的课表。请先打开“导入”页导入并核对。</p>
      </main>
    );
  }

  const coverage = timetable.source.coverage;
  const coverageWarning =
    coverage.completeness !== "complete" || coverage.scope !== "term";

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
            {WEEKDAY_LABELS.map((label) => (
              <th key={label}>周{label}</th>
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
                const cell = cells.get(`${weekdayIndex + 1}-${period.period}`);
                if (!cell) {
                  return <td key={weekdayIndex} />;
                }
                const color =
                  COURSE_COLORS[
                    Math.abs(hashCode(cell.courseTitle)) % COURSE_COLORS.length
                  ];
                return (
                  <td key={weekdayIndex} style={{ backgroundColor: color }}>
                    <strong>{cell.courseTitle}</strong>
                    <br />
                    {cell.location ?? "地点待确认"}
                    <br />
                    周次：{cell.weeks.join(",")}
                    {term.calendar_status !== "official_verified" && (
                      <>
                        <br />
                        <em>待确认</em>
                      </>
                    )}
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
