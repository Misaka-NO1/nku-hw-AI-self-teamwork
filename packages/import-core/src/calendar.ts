import type { TermCalendar } from "./types";

/**
 * 教学周/星期与实际日期的换算，以及调休规则应用（与后端 expand_occurrences 同一语义）。
 *
 * - date = week1_monday + 7*(week-1) + (weekday-1)；
 * - cancel：该实际日期无课程（返回 null）；
 * - replace：该实际日期改用指定 (teaching_week, weekday) 模板，不与原模板叠加。
 */

export function actualDateFor(term: TermCalendar, week: number, weekday: number): string {
  const mondayUtc = Date.parse(`${term.week1_monday}T00:00:00+08:00`);
  const shanghaiMs = mondayUtc + (7 * (week - 1) + (weekday - 1)) * 86_400_000 + 8 * 3_600_000;
  return new Date(shanghaiMs).toISOString().slice(0, 10);
}

export interface EffectiveTemplate {
  week: number;
  weekday: number;
  /** 是否被调休规则改写（cancel/replace） */
  overridden: boolean;
  sourceRef: string | null;
}

/** 返回某实际日期应使用的课程模板；cancel 时返回 null。 */
export function getEffectiveTemplate(
  term: TermCalendar,
  actualDate: string,
  week: number,
  weekday: number,
): EffectiveTemplate | null {
  for (const override of term.overrides) {
    if (override.date !== actualDate) continue;
    if (override.action === "cancel") {
      return null;
    }
    if (override.teaching_week !== null && override.weekday !== null) {
      return {
        week: override.teaching_week,
        weekday: override.weekday,
        overridden: true,
        sourceRef: override.source_ref,
      };
    }
  }
  return { week, weekday, overridden: false, sourceRef: null };
}

/** 以 +08:00 偏移输出当前时间（团队约定不使用 Z 后缀）。 */
export function shanghaiIsoNow(now: Date = new Date()): string {
  const shanghai = new Date(now.getTime() + 8 * 3_600_000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    `${shanghai.getUTCFullYear()}-${pad(shanghai.getUTCMonth() + 1)}-${pad(shanghai.getUTCDate())}` +
    `T${pad(shanghai.getUTCHours())}:${pad(shanghai.getUTCMinutes())}:${pad(shanghai.getUTCSeconds())}+08:00`
  );
}

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const CALENDAR_STATUSES = ["demo", "official_verified", "user_confirmed", "needs_confirmation"];

/**
 * 按 TermCalendar 契约校验完整结构（不只是“periods 是数组”）。
 * 防止畸形日历在导入解析时抛出未处理异常（PR #2 第三轮复审 P2）。
 */
export function validateTermCalendarStructure(value: unknown): { ok: boolean; errors: string[] } {
  const errors: string[] = [];
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { ok: false, errors: ["不是有效的 TermCalendar 对象"] };
  }
  const calendar = value as Record<string, unknown>;

  if (typeof calendar.term_id !== "string" || calendar.term_id.length === 0) {
    errors.push("term_id 必须是非空字符串");
  }
  if (calendar.timezone !== "Asia/Shanghai") {
    errors.push("timezone 必须为 Asia/Shanghai");
  }
  if (typeof calendar.week1_monday !== "string" || !DATE_PATTERN.test(calendar.week1_monday)) {
    errors.push("week1_monday 必须是 YYYY-MM-DD 日期");
  }
  if (
    typeof calendar.teaching_weeks !== "number" ||
    !Number.isInteger(calendar.teaching_weeks) ||
    calendar.teaching_weeks < 1
  ) {
    errors.push("teaching_weeks 必须是正整数");
  }
  if (!CALENDAR_STATUSES.includes(calendar.calendar_status as string)) {
    errors.push(`calendar_status 必须是 ${CALENDAR_STATUSES.join("/")} 之一`);
  }

  if (!Array.isArray(calendar.periods) || calendar.periods.length === 0) {
    errors.push("periods 必须是非空数组");
  } else {
    calendar.periods.forEach((period, index) => {
      if (typeof period !== "object" || period === null) {
        errors.push(`periods.${index} 不是有效节次对象`);
        return;
      }
      const item = period as Record<string, unknown>;
      if (typeof item.period !== "number" || !Number.isInteger(item.period) || item.period < 1) {
        errors.push(`periods.${index}.period 必须是正整数`);
      }
      if (typeof item.start !== "string" || !TIME_PATTERN.test(item.start)) {
        errors.push(`periods.${index}.start 必须是 HH:MM`);
      }
      if (typeof item.end !== "string" || !TIME_PATTERN.test(item.end)) {
        errors.push(`periods.${index}.end 必须是 HH:MM`);
      }
    });
  }

  if (!Array.isArray(calendar.overrides)) {
    errors.push("overrides 必须是数组");
  } else {
    calendar.overrides.forEach((override, index) => {
      if (typeof override !== "object" || override === null) {
        errors.push(`overrides.${index} 不是有效对象`);
        return;
      }
      const item = override as Record<string, unknown>;
      if (typeof item.date !== "string" || !DATE_PATTERN.test(item.date)) {
        errors.push(`overrides.${index}.date 必须是 YYYY-MM-DD 日期`);
      }
      if (item.action !== "cancel" && item.action !== "replace") {
        errors.push(`overrides.${index}.action 必须是 cancel 或 replace`);
      }
      const weekOk =
        item.teaching_week === null ||
        (typeof item.teaching_week === "number" &&
          Number.isInteger(item.teaching_week) &&
          item.teaching_week >= 1);
      if (!weekOk) {
        errors.push(`overrides.${index}.teaching_week 必须是 null 或正整数`);
      }
      const weekdayOk =
        item.weekday === null ||
        (typeof item.weekday === "number" &&
          Number.isInteger(item.weekday) &&
          item.weekday >= 1 &&
          item.weekday <= 7);
      if (!weekdayOk) {
        errors.push(`overrides.${index}.weekday 必须是 null 或 1..7`);
      }
      if (typeof item.source_ref !== "string") {
        errors.push(`overrides.${index}.source_ref 必须是字符串`);
      }
    });
  }

  if (typeof calendar.source_ref !== "string") {
    errors.push("source_ref 必须是字符串");
  }

  return { ok: errors.length === 0, errors };
}
