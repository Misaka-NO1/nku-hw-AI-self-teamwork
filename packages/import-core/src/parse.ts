import { recognizePage, unsupportedIssue } from "./adapters";
import { shanghaiIsoNow } from "./calendar";
import { normalizeCourses, parsePeriodRange, parseWeekday } from "./normalize";
import type { NormalizeOptions, RawMeetingRow } from "./normalize";
import { validateTimetableStructure } from "./schema";
import type {
  PageObservation,
  ParseIssue,
  ParseResult,
  TermCalendar,
  TimetableImport,
} from "./types";

/**
 * 文件/页面导入入口（B01/B04）。
 *
 * 安全约束：
 * - HTML 只用 DOMParser 提取文本，不执行脚本、不加载远程资源（IMPORT-03）；
 * - 文件超过团队配置（5MiB / 2000 行）直接报错，不截断硬解；
 * - 不支持的页面/表头返回 UNSUPPORTED_PAGE，绝不产出空课表（IMPORT-01）。
 */

export const IMPORT_LIMITS = {
  maxBytes: 5 * 1024 * 1024,
  maxLines: 2000,
};

export interface ImportFileInput {
  name: string;
  content: string;
}

export type ImportFormat = "json" | "csv" | "html";

const HEADER_ALIASES: Record<string, string[]> = {
  title: ["课程", "课程名称", "title"],
  weekday: ["星期", "weekday"],
  periods: ["节次", "periods"],
  weeks: ["周次", "weeks"],
  location: ["地点", "上课地点", "location"],
  teacher: ["教师", "授课教师", "teacher_display"],
  credits: ["学分", "credits"],
  courseId: ["课程编号", "course_id"],
  courseCode: ["课程代码", "course_code"],
};

export const REQUIRED_TABLE_HEADERS = ["课程", "星期", "节次", "周次"];

function headerIndex(headers: string[]): Record<string, number> {
  const index: Record<string, number> = {};
  for (const [key, aliases] of Object.entries(HEADER_ALIASES)) {
    const found = headers.findIndex((header) => aliases.includes(header.trim()));
    if (found >= 0) {
      index[key] = found;
    }
  }
  return index;
}

/** 把表头+文本行转换为 RawMeetingRow；表头不合法时返回 null（IMPORT-01）。 */
export function tableToRawRows(headers: string[], rows: string[][]): RawMeetingRow[] | null {
  const index = headerIndex(headers);
  if (index.title === undefined || index.weekday === undefined || index.periods === undefined || index.weeks === undefined) {
    return null;
  }
  const result: RawMeetingRow[] = [];
  for (const cells of rows) {
    const cell = (key: string): string | null => {
      const position = index[key];
      if (position === undefined) return null;
      const value = (cells[position] ?? "").trim();
      return value === "" ? null : value;
    };
    const weekdayRaw = cell("weekday") ?? "";
    const periodsRaw = cell("periods") ?? "";
    const weekday = parseWeekday(weekdayRaw);
    const periods = parsePeriodRange(periodsRaw);
    result.push({
      courseId: cell("courseId"),
      courseCode: cell("courseCode"),
      title: cell("title") ?? "",
      credits: cell("credits"),
      teacher: cell("teacher"),
      weekday: weekday ?? Number.NaN,
      weeksText: cell("weeks") ?? "",
      startPeriod: periods?.start ?? Number.NaN,
      endPeriod: periods?.end ?? Number.NaN,
      location: cell("location"),
      campusId: null,
    });
  }
  return result;
}

function blockingParseResult(
  issues: ParseIssue[],
  adapterId: string,
  adapterVersion: string,
): ParseResult {
  return { payload: null, issues, adapterId, adapterVersion };
}

function checkLimits(input: ImportFileInput): ParseIssue | null {
  const bytes = new TextEncoder().encode(input.content).length;
  if (bytes > IMPORT_LIMITS.maxBytes) {
    return {
      code: "file_too_large",
      field: "file",
      message: `文件超过 ${IMPORT_LIMITS.maxBytes} 字节上限`,
      blocking: true,
    };
  }
  if (input.content.split("\n").length > IMPORT_LIMITS.maxLines) {
    return {
      code: "file_too_large",
      field: "file",
      message: `文件超过 ${IMPORT_LIMITS.maxLines} 行上限`,
      blocking: true,
    };
  }
  return null;
}

/**
 * 标准 CSV 解析：按字符流处理，引号内允许换行、逗号与双引号转义（""）。
 * 不能先按换行切分，否则引号内带换行的字段会被截断（PR #2 审核意见 6）。
 */
function parseCsvRecords(content: string): string[][] {
  const records: string[][] = [];
  let field = "";
  let record: string[] = [];
  let inQuotes = false;
  let i = 0;
  while (i < content.length) {
    const char = content[i];
    if (inQuotes) {
      if (char === '"') {
        if (content[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      record.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && content[i + 1] === "\n") {
        i += 1;
      }
      record.push(field);
      field = "";
      records.push(record);
      record = [];
    } else {
      field += char;
    }
    i += 1;
  }
  if (field !== "" || record.length > 0) {
    record.push(field);
    records.push(record);
  }
  return records
    .filter((cells) => cells.some((cell) => cell.trim() !== ""))
    .map((cells) => cells.map((cell) => cell.trim()));
}

function parseCsv(content: string): { headers: string[]; rows: string[][] } {
  const records = parseCsvRecords(content);
  const headers = records.length > 0 ? records[0] : [];
  return { headers, rows: records.slice(1) };
}

/**
 * 从 HTML 中提取课表表格。只读取文本内容（textContent），
 * DOMParser 不执行脚本、不请求远程资源。
 */
export function extractHtmlTable(content: string): { headers: string[]; rows: string[][] } | null {
  const doc = new DOMParser().parseFromString(content, "text/html");
  const tables = [...doc.querySelectorAll("table")];
  for (const table of tables) {
    const headerCells = [...table.querySelectorAll("thead th, thead td")].map((cell) =>
      (cell.textContent ?? "").trim(),
    );
    const firstRowCells =
      headerCells.length > 0
        ? headerCells
        : [...(table.querySelector("tr")?.querySelectorAll("th,td") ?? [])].map((cell) =>
            (cell.textContent ?? "").trim(),
          );
    if (!REQUIRED_TABLE_HEADERS.every((header) => firstRowCells.includes(header))) {
      continue;
    }
    const allRows = [...table.querySelectorAll("tr")];
    // 表头行（全部为 th）不作为数据行；jsdom 会把 tr 自动包进 tbody，不能靠位置排除
    const rows = allRows
      .filter((row) => {
        const cells = [...row.querySelectorAll("th,td")];
        return cells.length > 0 && cells.some((cell) => cell.tagName.toLowerCase() !== "th");
      })
      .map((row) => [...row.querySelectorAll("th,td")].map((cell) => (cell.textContent ?? "").trim()));
    return { headers: firstRowCells, rows };
  }
  return null;
}

export function parseImportFile(
  input: ImportFileInput,
  format: ImportFormat,
  calendar: TermCalendar,
  options?: { datasetKind?: "demo" | "personal"; capturedAt?: string },
): ParseResult {
  const adapterId = "file-import";
  const adapterVersion = "1.0.0";

  const limitIssue = checkLimits(input);
  if (limitIssue) {
    return blockingParseResult([limitIssue], adapterId, adapterVersion);
  }

  const capturedAt = options?.capturedAt ?? shanghaiIsoNow();
  const normalizeOptions: Omit<NormalizeOptions, "kind" | "completenessHint"> = {
    calendar,
    adapterId,
    adapterVersion,
    capturedAt,
    datasetKind: options?.datasetKind ?? "demo",
  };

  if (format === "json") {
    let parsed: unknown;
    try {
      parsed = JSON.parse(input.content);
    } catch {
      return blockingParseResult(
        [{ code: "invalid_json", field: "file", message: "JSON 解析失败", blocking: true }],
        adapterId,
        adapterVersion,
      );
    }
    return normalizeJsonPayload(parsed, normalizeOptions);
  }

  const table = format === "csv" ? parseCsv(input.content) : extractHtmlTable(input.content);
  if (table === null || table.headers.length === 0) {
    return blockingParseResult(
      [unsupportedIssue("无法识别的表头或空文件，拒绝导入空课表")],
      adapterId,
      adapterVersion,
    );
  }
  const rows = tableToRawRows(table.headers, table.rows);
  if (rows === null) {
    return blockingParseResult(
      [unsupportedIssue("缺少必需表头（课程/星期/节次/周次），拒绝导入")],
      adapterId,
      adapterVersion,
    );
  }
  return normalizeCourses(rows, { ...normalizeOptions, kind: "file", completenessHint: "unknown" });
}

function normalizeJsonPayload(
  parsed: unknown,
  options: Omit<NormalizeOptions, "kind" | "completenessHint">,
): ParseResult {
  if (typeof parsed !== "object" || parsed === null) {
    return blockingParseResult(
      [{ code: "invalid_json", field: "file", message: "JSON 不是对象", blocking: true }],
      options.adapterId,
      options.adapterVersion,
    );
  }
  // 标准 JSON 导入直接接受 TimetableImport 结构；周次等语义校验在后端 validate_timetable 复核
  const candidate = parsed as { courses?: unknown; source?: { coverage?: unknown } };
  if (!Array.isArray(candidate.courses) || candidate.courses.length === 0) {
    return blockingParseResult(
      [
        {
          code: "empty_timetable",
          field: "courses",
          message: "JSON 中没有课程，拒绝导入空课表",
          blocking: true,
        },
      ],
      options.adapterId,
      options.adapterVersion,
    );
  }
  const payload = parsed as TimetableImport;
  const violations = validateTimetableStructure(payload);
  if (violations.length > 0) {
    return blockingParseResult(
      violations.map((violation) => ({
        code: "schema_violation",
        field: violation.field,
        message: violation.message,
        blocking: true,
      })),
      options.adapterId,
      options.adapterVersion,
    );
  }
  return {
    payload,
    issues: [],
    adapterId: options.adapterId,
    adapterVersion: options.adapterVersion,
  };
}

/** 扩展路径：先识别页面，再用课程区域观察值解析（B06/B08）。 */
export function parseObservation(
  observation: PageObservation,
  calendar: TermCalendar,
  options?: { datasetKind?: "demo" | "personal"; capturedAt?: string },
): ParseResult {
  const recognition = recognizePage(observation);
  if (!recognition.supported || recognition.adapterId === null) {
    return blockingParseResult(
      [unsupportedIssue(recognition.reason)],
      recognition.adapterId ?? "none",
      "0.0.0",
    );
  }
  const rows = tableToRawRows(observation.tableHeaders, observation.rows);
  if (rows === null) {
    return blockingParseResult(
      [unsupportedIssue("课程表结构不符合适配器预期（可能页面已改版），请改用文件导入")],
      recognition.adapterId,
      "1.0.0",
    );
  }
  // 只抓到当前周/分页/虚拟列表时必须标 partial，不能标 complete
  const completeness =
    observation.hasPagination || observation.hasVirtualRows
      ? "partial"
      : observation.selectedWeeks.length > 0
        ? "unknown"
        : "complete";
  const result = normalizeCourses(rows, {
    calendar,
    kind: "visible_dom",
    adapterId: recognition.adapterId,
    adapterVersion: "1.0.0",
    capturedAt: options?.capturedAt ?? shanghaiIsoNow(),
    datasetKind: options?.datasetKind ?? "personal",
    completenessHint: completeness,
  });
  if (result.payload && observation.selectedWeeks.length > 0) {
    result.payload.source.coverage = {
      scope: "selected_weeks",
      week_numbers: [...observation.selectedWeeks].sort((a, b) => a - b),
      completeness: completeness === "complete" ? "unknown" : completeness,
    };
  }
  return result;
}
