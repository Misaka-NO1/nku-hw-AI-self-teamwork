import { describe, expect, it } from "vitest";

import { parseWeeks } from "../src/weeks";

describe("parseWeeks（B02）", () => {
  it("解析连续区间", () => {
    expect(parseWeeks("1-16").weeks).toEqual(Array.from({ length: 16 }, (_, i) => i + 1));
  });

  it("解析单周（奇数周）", () => {
    expect(parseWeeks("1-16单周").weeks).toEqual([1, 3, 5, 7, 9, 11, 13, 15]);
    expect(parseWeeks("1-8单").weeks).toEqual([1, 3, 5, 7]);
  });

  it("解析双周（偶数周）", () => {
    expect(parseWeeks("1-16双周").weeks).toEqual([2, 4, 6, 8, 10, 12, 14, 16]);
  });

  it("解析跳周与组合", () => {
    expect(parseWeeks("1,3,5-9").weeks).toEqual([1, 3, 5, 6, 7, 8, 9]);
  });

  it("兼容中文标点与全角分隔符", () => {
    expect(parseWeeks("1，3、5—9 双").weeks).toEqual([6, 8]);
    expect(parseWeeks("1～4单周").weeks).toEqual([1, 3]);
    expect(parseWeeks("2到8双周").weeks).toEqual([2, 4, 6, 8]);
  });

  it("结果去重且升序", () => {
    expect(parseWeeks("3,1,3,2").weeks).toEqual([1, 2, 3]);
  });

  it("非法周次返回 blocking issue 而不是猜测", () => {
    for (const bad of ["", "abc", "0", "5-2", "-3", "1.5", "第3周"]) {
      const result = parseWeeks(bad);
      expect(result.weeks).toBeNull();
      expect(result.issues.some((issue) => issue.blocking)).toBe(true);
    }
  });

  it("超出教学周范围时报 week_out_of_range", () => {
    const result = parseWeeks("1-9", 4);
    expect(result.weeks).toBeNull();
    expect(result.issues[0].code).toBe("week_out_of_range");
  });
});
