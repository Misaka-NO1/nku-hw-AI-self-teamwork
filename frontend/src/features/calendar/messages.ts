import { ApiError } from "../../shared/api/client";

const timetableExpired = "课表有效期已结束，无法据此推荐当前时间。请先更新课表，再重新计算候选；现有待办记录不会因此删除。";
const labels: Record<string, string> = {
  timetable_outside_term: timetableExpired,
  source_review: "核对原通知",
  due_time: "补充具体截止时间",
  estimated_minutes: "补充预计耗时",
  earliest_start: "确认最早可开始时间",
  reference_date: "确认通知所指的参照日期",
};

export function confirmationText(reason: string): string {
  return labels[reason] ?? reason;
}

/** Preserve unknown errors and request IDs; do not infer expiry from HTTP status. */
export function calendarErrorText(error: unknown): string {
  if (!(error instanceof Error)) return "请求失败，请重试";
  const outsideTerm = error instanceof ApiError && (
    error.fieldErrors.some(field => field.code.toLowerCase() === "timetable_outside_term")
    || /\btimetable_outside_term\b/i.test(error.message)
  );
  const message = outsideTerm ? timetableExpired : error.message;
  return message + (error instanceof ApiError && error.requestId ? `（${error.requestId}）` : "");
}
