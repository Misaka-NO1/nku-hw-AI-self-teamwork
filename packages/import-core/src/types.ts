/**
 * import-core 共享类型。
 *
 * 注意：TimetableImport 等对外 JSON 结构固定使用 snake_case（契约 v1.0.0）；
 * adapterId / adapterVersion 只允许存在于 TS 内部结果（ParseResult），
 * 写入标准 JSON 前必须转换为 adapter_id / adapter_version。
 */

export interface Coverage {
  scope: "term" | "selected_weeks" | "unknown";
  week_numbers: number[];
  completeness: "complete" | "partial" | "unknown";
}

export interface TermPeriod {
  period: number;
  start: string; // "HH:MM"
  end: string;
}

export interface TermOverride {
  date: string;
  action: "cancel" | "replace";
  teaching_week: number | null;
  weekday: number | null;
  source_ref: string;
}

export interface TermCalendar {
  term_id: string;
  timezone: "Asia/Shanghai";
  week1_monday: string;
  teaching_weeks: number;
  calendar_status: "demo" | "official_verified" | "user_confirmed" | "needs_confirmation";
  periods: TermPeriod[];
  overrides: TermOverride[];
  source_ref: string;
}

export interface Meeting {
  meeting_id: string;
  weekday: number;
  weeks: number[];
  start_period: number;
  end_period: number;
  location: string | null;
  campus_id: string | null;
}

export interface Course {
  course_id: string;
  course_code: string | null;
  offering_id: string;
  title: string;
  credits: string | null;
  teacher_display: string | null;
  meetings: Meeting[];
}

export interface TimetableSource {
  kind: "fixture" | "visible_dom" | "file";
  adapter_id: string | null;
  adapter_version: string | null;
  captured_at: string;
  coverage: Coverage;
}

export interface TimetableImport {
  schema_version: "1.0.0";
  dataset_kind: "demo" | "personal";
  term: TermCalendar;
  source: TimetableSource;
  courses: Course[];
}

/** 扩展 content script 只允许回传的白名单课程区域观察值，不是整页 HTML。 */
export interface PageObservation {
  origin: string;
  pathname: string;
  frameOrigin: string | null;
  tableHeaders: string[];
  rows: string[][];
  selectedTerm: string | null;
  selectedWeeks: number[];
  hasPagination: boolean;
  hasVirtualRows: boolean;
}

export interface ParseIssue {
  code: string;
  field: string;
  message: string;
  blocking: boolean;
}

export interface ParseResult {
  /** 成功时为符合契约的 TimetableImport（snake_case）；失败时为 null */
  payload: TimetableImport | null;
  issues: ParseIssue[];
  adapterId: string;
  adapterVersion: string;
}
