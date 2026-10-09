import type { RawMeetingRow } from "./normalize";
import { parseWeekday } from "./normalize";
import type { PageObservation, ParseIssue } from "./types";
import { parseWeeks } from "./weeks";

/** eamis 课表网格选择器与页面原始表头特征（2026-10-07 核查）。 */
export const EAMIS_GRID_SELECTOR = "#manualArrangeCourseTable";
export const EAMIS_GRID_PAGE_HEADERS = ["节次/周次", "星期一", "星期日"];

/** 统一身份认证（SSO）登录页特征：另存到登录页时给出可操作提示而非笼统的 UNSUPPORTED_PAGE。 */
const SSO_PAGE_MARKERS = ["统一身份认证", "authserver", "sso"];

export function looksLikeSsoLoginPage(doc: Document): boolean {
  const title = doc.title ?? "";
  if (SSO_PAGE_MARKERS.some((marker) => title.includes(marker))) return true;
  const bodyText = (doc.body?.textContent ?? "").slice(0, 2000);
  return bodyText.includes("统一身份认证") && !doc.querySelector(EAMIS_GRID_SELECTOR);
}

/**
 * 从 DOM（真实页面或另存的 HTML 文件）提取 eamis 网格。
 * rowSpan 展开为「p-q」节次范围；行头格（真实页面是 td）跳过；
 * 合并格只输出一次。表头特征不符返回 null（页面改版）。
 */
export function extractEamisGridFromDoc(
  doc: Document,
): { headers: string[]; rows: string[][] } | null {
  const table = doc.querySelector<HTMLTableElement>(EAMIS_GRID_SELECTOR);
  if (!table) return null;
  const headerRow = table.querySelector("tr");
  const headerTexts = [...(headerRow?.querySelectorAll("th,td") ?? [])].map((cell) =>
    (cell.textContent ?? "").trim(),
  );
  if (!EAMIS_GRID_PAGE_HEADERS.every((header) => headerTexts.includes(header))) {
    return null;
  }
  const weekdayLabels = headerTexts.slice(1); // 星期一..星期日
  const rows: string[][] = [];
  const emitted = new Set<string>();
  // Occupancy is independent of text, including empty merged cells. Track the
  // actual end row; carrying a cell for only one row shifts later courses.
  const occupiedUntil: number[] = new Array(weekdayLabels.length).fill(0);

  const periodRows = [...table.querySelectorAll("tr")].slice(1);
  periodRows.forEach((row, rowIndex) => {
    const period = rowIndex + 1;
    const spans: (string | null)[] = new Array(weekdayLabels.length).fill(null);
    // row.children[0] 是节次行头（th 或 td），必须跳过——真实页面该格是 td。
    let column = 0;
    const dataCells = Array.from(row.children).slice(1) as HTMLTableCellElement[];
    for (const cell of dataCells) {
      while (column < spans.length && occupiedUntil[column] >= period) {
        column += 1;
      }
      if (column >= spans.length) break;
      const text = (cell.textContent ?? "").trim();
      const span = cell.rowSpan > 1 ? cell.rowSpan : 1;
      if(cell.colSpan>1 || period+span-1>periodRows.length) throw new Error("课表合并格结构不受支持，请核对原页或改用标准文件");
      spans[column] = text === "" ? null : `${text}@@${period}-${period + span - 1}`;
      occupiedUntil[column]=period+span-1;
      column += 1;
    }
    spans.forEach((entry, weekdayIndex) => {
      if (entry === null) return;
      const key = `${weekdayIndex}|${entry}`;
      if (emitted.has(key)) return; // rowSpan 合并格只输出一次
      emitted.add(key);
      const split=entry.lastIndexOf("@@");
      const text=entry.slice(0,split),spanRange=entry.slice(split+2);
      rows.push([text, weekdayLabels[weekdayIndex] ?? String(weekdayIndex + 1), spanRange]);
    });
  });
  return { headers: [...EAMIS_OBSERVATION_HEADERS], rows };
}


/**
 * nku-adapter-v1：eamis「我的课表」网格观察值解析（B08）。
 *
 * 结构依据 docs/evidence/B/adapter-observation.md（2026-10-07 本人只读核查）：
 * - 页面网格 table#manualArrangeCourseTable：行=节次（14 节）、列=星期（一~日）；
 * - 跨节课程用 rowSpan 合并，由 content script 展开为「课程条目/星期/节次」三列观察值；
 * - 单元格文本：`课程名称(序号) (教师)(周次,地点)`，同格多条目直接拼接；
 *   停课条目为 `(周次,停课)`，忽略并记录非阻塞 issue；
 * - 地点可含逗号分隔的多个地点与「组N」后缀，周次写法见 weeks.ts。
 *
 * 绝不猜测：条目无法完整解析时给出 blocking issue，不产出半解析数据。
 */

/** content script 提取 eamis 网格后输出的观察值表头（提取契约，非页面原始表头）。 */
export const EAMIS_OBSERVATION_HEADERS = ["课程条目", "星期", "节次"] as const;

export interface EamisConvertResult {
  rows: RawMeetingRow[];
  issues: ParseIssue[];
}

/**
 * 单条目正则：名称（可含全角括号）+ 半角(序号) + 空格+(教师) + (周次,地点)。
 * 序号锚定为 3 位以上数字，避免误切课程名中的括号。
 */
const ENTRY_RE = /(.+?)\((\d{3,})\)\s*\(([^)]*)\)\(([^)]*)\)/g;

/** 解析单个单元格文本为若干条目；返回 null 表示存在无法解析的残留文本。 */
export function parseEamisCellEntries(
  cellText: string,
): { entries: EamisCellEntry[]; residue: string | null } {
  const entries: EamisCellEntry[] = [];
  let cursor = 0;
  ENTRY_RE.lastIndex = 0;
  let match = ENTRY_RE.exec(cellText);
  while (match !== null) {
    const between = cellText.slice(cursor, match.index).trim();
    if (between !== "") {
      return { entries, residue: between };
    }
    entries.push({
      title: match[1].trim(),
      sequence: match[2],
      teacher: match[3].trim() === "" ? null : match[3].trim(),
      weeksAndLocation: match[4].trim(),
    });
    cursor = match.index + match[0].length;
    match = ENTRY_RE.exec(cellText);
  }
  const tail = cellText.slice(cursor).trim();
  return { entries, residue: tail === "" ? null : tail };
}

export interface EamisCellEntry {
  title: string;
  sequence: string;
  teacher: string | null;
  weeksAndLocation: string;
}

/**
 * 把 eamis 三列观察值转换为 RawMeetingRow。
 * - 星期列支持「星期一」或数字 1..7；
 * - 节次列为展开后的「p」或「p-q」；
 * - 停课条目（地点恰为「停课」）不产出 meeting，记录非阻塞 issue；
 * - 残留文本/非法星期/非法节次给 blocking issue。
 */
export function eamisObservationToRawRows(observation: PageObservation): EamisConvertResult {
  const issues: ParseIssue[] = [];
  const rows: RawMeetingRow[] = [];
  const cancellations: {courseId:string;weekday:number;startPeriod:number;endPeriod:number;weeks:number[]}[]=[];

  const headers = observation.tableHeaders.map((header) => header.trim());
  const idxEntry = headers.indexOf(EAMIS_OBSERVATION_HEADERS[0]);
  const idxWeekday = headers.indexOf(EAMIS_OBSERVATION_HEADERS[1]);
  const idxPeriods = headers.indexOf(EAMIS_OBSERVATION_HEADERS[2]);
  if (idxEntry < 0 || idxWeekday < 0 || idxPeriods < 0) {
    issues.push({
      code: "UNSUPPORTED_PAGE",
      field: "page",
      message: "UNSUPPORTED_PAGE: 观察值表头不符合 eamis 提取契约（可能页面已改版）",
      blocking: true,
    });
    return { rows, issues };
  }

  observation.rows.forEach((cells, rowIndex) => {
    const field = `rows.${rowIndex}`;
    const cellText = (cells[idxEntry] ?? "").trim();
    if (cellText === "") {
      return;
    }
    const weekday = parseWeekday((cells[idxWeekday] ?? "").trim());
    if (weekday === null) {
      issues.push({
        code: "invalid_weekday",
        field: `${field}.weekday`,
        message: `无法解析星期：${cells[idxWeekday] ?? ""}`,
        blocking: true,
      });
      return;
    }
    const periodMatch = (cells[idxPeriods] ?? "").trim().match(/^(\d{1,2})(?:-(\d{1,2}))?$/);
    if (!periodMatch) {
      issues.push({
        code: "invalid_periods",
        field: `${field}.periods`,
        message: `无法解析节次：${cells[idxPeriods] ?? ""}`,
        blocking: true,
      });
      return;
    }
    const startPeriod = Number(periodMatch[1]);
    const endPeriod = periodMatch[2] ? Number(periodMatch[2]) : startPeriod;

    const { entries, residue } = parseEamisCellEntries(cellText);
    if (residue !== null || entries.length === 0) {
      issues.push({
        code: "unparsable_cell",
        field,
        message: `课程条目无法完整解析（残留：${residue ?? cellText.slice(0, 30)}），已阻止导入，请改用文件导入`,
        blocking: true,
      });
      return;
    }

    for (const entry of entries) {
      const commaIndex = entry.weeksAndLocation.indexOf(",");
      if (commaIndex < 0) {
        issues.push({
          code: "unparsable_cell",
          field,
          message: `条目缺少「周次,地点」分隔：${entry.title}(${entry.sequence})`,
          blocking: true,
        });
        continue;
      }
      const weeksText = entry.weeksAndLocation.slice(0, commaIndex).trim();
      const location = entry.weeksAndLocation.slice(commaIndex + 1).trim();
      if (location === "停课") {
        const parsed=parseWeeks(weeksText);
        if(!parsed.weeks){issues.push({code:"invalid_weeks",field,message:"停课周次无法解析，请核对",blocking:true});continue;}
        cancellations.push({courseId:`eamis-${entry.sequence}`,weekday,startPeriod,endPeriod,weeks:parsed.weeks});
        issues.push({
          code: "cancelled_meeting",
          field,
          message: `已按页面「停课」标记忽略：${entry.title} 第${weeksText}周 周${weekday} 第${startPeriod}-${endPeriod}节`,
          blocking: false,
        });
        continue;
      }
      rows.push({
        courseId: `eamis-${entry.sequence}`,
        // Grid parentheses contain the offering sequence, not the course code.
        // Don't display that sequence as an official course code.
        courseCode: null,
        title: entry.title,
        credits: null,
        teacher: entry.teacher,
        weekday,
        weeksText,
        startPeriod,
        endPeriod,
        location: location === "" ? null : location,
        campusId: null,
      });
    }
  });

  const active=rows.flatMap(row=>{
    const cancelled=cancellations.filter(c=>c.courseId===row.courseId && c.weekday===row.weekday && c.startPeriod===row.startPeriod && c.endPeriod===row.endPeriod);
    if(!cancelled.length)return [row];
    const parsed=parseWeeks(row.weeksText);
    if(!parsed.weeks)return [row]; // normalizer reports the invalid active weeks
    const weeks=parsed.weeks.filter(w=>!cancelled.some(c=>c.weeks.includes(w)));
    return weeks.length ? [{...row,weeksText:weeks.join(",")}] : [];
  });
  return { rows:active, issues };
}
