import { validateTimetableStructure } from "./schema";
import { parseWeeks } from "./weeks";
import type {
  Course,
  Meeting,
  ParseIssue,
  ParseResult,
  TermCalendar,
  TimetableImport,
} from "./types";

/**
 * 把已解析出的“行”规范化为符合契约的 TimetableImport（B01/B02）。
 *
 * - 原文周次（含单双周、跳周、中文标点）由纯解析器转换为去重升序数组；
 * - 非法周次/节次给出 blocking issue，绝不修成猜测值；
 * - 同一 course 的不同 meeting 全部保留；完全重复的 meeting 去重并记录 issue；
 * - 无法确定的字段（地点/教师/学分）保持 null 并进入缺失列表，不虚构。
 */

export interface RawMeetingRow {
  courseId: string | null;
  courseCode: string | null;
  title: string;
  credits: string | null;
  teacher: string | null;
  weekday: number;
  weeksText: string;
  startPeriod: number;
  endPeriod: number;
  location: string | null;
  campusId: string | null;
}

export interface NormalizeOptions {
  calendar: TermCalendar;
  kind: "fixture" | "visible_dom" | "file";
  adapterId: string;
  adapterVersion: string;
  capturedAt: string;
  datasetKind: "demo" | "personal";
  /** 只抓到部分分页/当前周/虚拟列表时必须为 partial */
  completenessHint: "complete" | "partial" | "unknown";
}

const WEEKDAY_ALIASES: Record<string, number> = {
  一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 日: 7, 天: 7,
};

export function parseWeekday(raw: string): number | null {
  const text = raw.trim();
  if (/^[1-7]$/.test(text)) {
    return Number(text);
  }
  const match = text.match(/^(?:周|星期)?([一二三四五六日天])$/);
  if (match) {
    return WEEKDAY_ALIASES[match[1]] ?? null;
  }
  return null;
}

export function parsePeriodRange(raw: string): { start: number; end: number } | null {
  const match = raw.trim().match(/^(\d{1,2})\s*[-–—~～]?\s*(\d{1,2})?$/);
  if (!match) {
    return null;
  }
  const start = Number(match[1]);
  const end = match[2] ? Number(match[2]) : start;
  if (start < 1 || end < start) {
    return null;
  }
  return { start, end };
}

export function normalizeCourses(rows: RawMeetingRow[], options: NormalizeOptions): ParseResult {
  const issues: ParseIssue[] = [];
  const { calendar } = options;
  const periodNumbers = new Set(calendar.periods.map((period) => period.period));

  const coursesByKey = new Map<string, Course>();

  rows.forEach((row, index) => {
    const field = `rows.${index}`;
    if (!row.title.trim()) {
      issues.push({ code: "missing_title", field: `${field}.title`, message: "课程名为空", blocking: true });
      return;
    }
    const weeksResult = parseWeeks(row.weeksText, calendar.teaching_weeks);
    issues.push(...weeksResult.issues.map((issue) => ({ ...issue, field: `${field}.weeks` })));
    if (weeksResult.weeks === null) {
      return;
    }
    if (row.weekday < 1 || row.weekday > 7) {
      issues.push({ code: "invalid_weekday", field: `${field}.weekday`, message: "星期必须在 1..7", blocking: true });
      return;
    }
    if (row.startPeriod > row.endPeriod) {
      issues.push({
        code: "period_order",
        field,
        message: "start_period 不能大于 end_period",
        blocking: true,
      });
      return;
    }
    if (!periodNumbers.has(row.startPeriod) || !periodNumbers.has(row.endPeriod)) {
      issues.push({
        code: "unknown_period",
        field,
        message: "节次不存在于学期日历中",
        blocking: true,
      });
      return;
    }

    const courseId = row.courseId ?? `imported-${index}`;
    const meeting: Meeting = {
      meeting_id: `${courseId}-m${index}`,
      weekday: row.weekday,
      weeks: weeksResult.weeks,
      start_period: row.startPeriod,
      end_period: row.endPeriod,
      location: row.location,
      campus_id: row.campusId,
    };

    const missing: string[] = [];
    if (row.location === null) missing.push("location");
    if (row.teacher === null) missing.push("teacher_display");
    if (row.credits === null) missing.push("credits");
    if (missing.length > 0) {
      issues.push({
        code: "missing_fields",
        field,
        message: `缺失字段保持待确认：${missing.join(",")}`,
        blocking: false,
      });
    }

    let course = coursesByKey.get(courseId);
    if (!course) {
      course = {
        course_id: courseId,
        course_code: row.courseCode,
        offering_id: `${courseId}-${calendar.term_id}`,
        title: row.title.trim(),
        credits: row.credits,
        teacher_display: row.teacher,
        meetings: [],
      };
      coursesByKey.set(courseId, course);
    }
    // IMPORT-02：同课程不同 meeting 全部保留；仅完全重复才去掉
    const signature = JSON.stringify({ ...meeting, meeting_id: "" });
    const duplicated = course.meetings.some(
      (existing) => JSON.stringify({ ...existing, meeting_id: "" }) === signature,
    );
    if (duplicated) {
      issues.push({
        code: "duplicate_meeting",
        field,
        message: "完全重复的 meeting 已去重",
        blocking: false,
      });
      return;
    }
    meeting.meeting_id = `${courseId}-m${course.meetings.length + 1}`;
    course.meetings.push(meeting);
  });

  if (issues.some((issue) => issue.blocking)) {
    return { payload: null, issues, adapterId: options.adapterId, adapterVersion: options.adapterVersion };
  }

  const courses = [...coursesByKey.values()];
  if (courses.length === 0) {
    issues.push({ code: "empty_timetable", field: "rows", message: "没有任何可导入的课程，拒绝导入空课表", blocking: true });
    return { payload: null, issues, adapterId: options.adapterId, adapterVersion: options.adapterVersion };
  }

  const weekNumbers = [
    ...new Set(courses.flatMap((course) => course.meetings.flatMap((meeting) => meeting.weeks))),
  ].sort((a, b) => a - b);
  const fullCoverage =
    weekNumbers.length === calendar.teaching_weeks &&
    weekNumbers.every((week, i) => week === i + 1);

  const payload: TimetableImport = {
    schema_version: "1.0.0",
    dataset_kind: options.datasetKind,
    term: calendar,
    source: {
      kind: options.kind,
      adapter_id: options.adapterId,
      adapter_version: options.adapterVersion,
      captured_at: options.capturedAt,
      coverage: {
        scope: fullCoverage ? "term" : "selected_weeks",
        week_numbers: weekNumbers,
        completeness: options.completenessHint,
      },
    },
    courses,
  };

  const violations = validateTimetableStructure(payload);
  for (const violation of violations) {
    issues.push({
      code: "schema_violation",
      field: violation.field,
      message: violation.message,
      blocking: true,
    });
  }
  if (violations.length > 0) {
    return { payload: null, issues, adapterId: options.adapterId, adapterVersion: options.adapterVersion };
  }

  return { payload, issues, adapterId: options.adapterId, adapterVersion: options.adapterVersion };
}
