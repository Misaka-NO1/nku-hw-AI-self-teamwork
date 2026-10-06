import { describe, expect, it } from "vitest";
import { ApiError } from "../../shared/api/client";
import { calendarErrorText, confirmationText } from "./messages";

const failure = (message: string, code?: string) => new ApiError({
  code: "VALIDATION_ERROR", status: 422, message, requestId: "calendar-expired-test",
  fieldErrors: code ? [{ field: "timetable", code, message: "Coverage failed" }] : [],
});
describe("calendar integration messages", () => {
  it("explains explicit expired timetable reason and preserves request ID", () => {
    const text = calendarErrorText(failure("Cannot schedule: timetable_outside_term"));
    expect(text).toContain("课表有效期已结束");
    expect(text).toContain("更新课表");
    expect(text).toContain("calendar-expired-test");
  });
  it("recognizes the reason in structured field errors", () => {
    expect(calendarErrorText(failure("Coverage failed", "TIMETABLE_OUTSIDE_TERM"))).toContain("课表有效期已结束");
  });
  it("does not classify arbitrary validation failures as an expired term", () => {
    expect(calendarErrorText(failure("Invalid duration"))).toBe("Invalid duration（calendar-expired-test）");
    expect(calendarErrorText(new Error("Unexpected error"))).toBe("Unexpected error");
  });
  it("explains known confirmation keys without hiding new backend reasons", () => {
    expect(confirmationText("estimated_minutes")).toBe("补充预计耗时");
    expect(confirmationText("reference_date")).toBe("确认通知所指的参照日期");
    expect(confirmationText("timetable_outside_term")).toContain("无法据此推荐当前时间");
    expect(confirmationText("future_backend_reason")).toBe("future_backend_reason");
  });
});
