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
