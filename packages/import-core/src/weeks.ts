import type { ParseIssue } from "./types";

/**
 * 通用周次解析（B02）。
 *
 * 支持："1-16"、"1–16"、"1—16"、"1~16"、"1到16"、逗号/中文逗号/顿号分隔、
 * "单周"/"单"、"双周"/"双"、跳周（如 "1,3,5-9双"）。
 * 非法输入（非数字、0、负数、空）返回 weeks=null 并给出 blocking issue，
 * 绝不猜测成看似合理的周次。
 */

export interface WeeksParseResult {
  weeks: number[] | null;
  issues: ParseIssue[];
}

const RANGE_SEPARATORS = ["-", "–", "—", "~", "～", "到", "至"];

export function parseWeeks(raw: string, teachingWeeks?: number): WeeksParseResult {
  const issues: ParseIssue[] = [];
  const text = raw.trim();
  if (!text) {
    issues.push({ code: "invalid_weeks", field: "weeks", message: "周次为空", blocking: true });
    return { weeks: null, issues };
  }

  let parity: "odd" | "even" | null = null;
  let body = text;
  if (/单周?$/.test(body)) {
    parity = "odd";
    body = body.replace(/单周?$/, "");
  } else if (/双周?$/.test(body)) {
    parity = "even";
    body = body.replace(/双周?$/, "");
  }

  const weeks = new Set<number>();
  const segments = body.split(/[,，、;；\s]+/).filter((part) => part.length > 0);
  if (segments.length === 0) {
    issues.push({ code: "invalid_weeks", field: "weeks", message: `无法解析周次：${raw}`, blocking: true });
    return { weeks: null, issues };
  }

  for (const segment of segments) {
    const separator = RANGE_SEPARATORS.find((sep) => segment.includes(sep));
    if (separator) {
      const [startRaw, endRaw, ...rest] = segment.split(separator);
      if (rest.length > 0 || !/^\d+$/.test(startRaw.trim()) || !/^\d+$/.test(endRaw.trim())) {
        issues.push({
          code: "invalid_weeks",
          field: "weeks",
          message: `无法解析周次区间：${segment}`,
          blocking: true,
        });
        return { weeks: null, issues };
      }
      const start = Number(startRaw.trim());
      const end = Number(endRaw.trim());
      if (start < 1 || end < 1 || start > end) {
        issues.push({
          code: "invalid_weeks",
          field: "weeks",
          message: `非法周次区间：${segment}`,
          blocking: true,
        });
        return { weeks: null, issues };
      }
      for (let week = start; week <= end; week += 1) {
        weeks.add(week);
      }
    } else if (/^\d+$/.test(segment)) {
      const week = Number(segment);
      if (week < 1) {
        issues.push({
          code: "invalid_weeks",
          field: "weeks",
          message: `非法周次：${segment}`,
          blocking: true,
        });
        return { weeks: null, issues };
      }
      weeks.add(week);
    } else {
      issues.push({
        code: "invalid_weeks",
        field: "weeks",
        message: `无法解析周次：${segment}`,
        blocking: true,
      });
      return { weeks: null, issues };
    }
  }

  let result = [...weeks];
  if (parity === "odd") {
    result = result.filter((week) => week % 2 === 1);
  } else if (parity === "even") {
    result = result.filter((week) => week % 2 === 0);
  }
  result = [...new Set(result)].sort((a, b) => a - b);

  if (result.length === 0) {
    issues.push({
      code: "invalid_weeks",
      field: "weeks",
      message: `周次过滤后为空：${raw}`,
      blocking: true,
    });
    return { weeks: null, issues };
  }

  if (teachingWeeks !== undefined) {
    const outOfRange = result.filter((week) => week > teachingWeeks);
    if (outOfRange.length > 0) {
      issues.push({
        code: "week_out_of_range",
        field: "weeks",
        message: `周次 ${outOfRange.join(",")} 超出教学周范围 1..${teachingWeeks}`,
        blocking: true,
      });
      return { weeks: null, issues };
    }
  }

  return { weeks: result, issues };
}
