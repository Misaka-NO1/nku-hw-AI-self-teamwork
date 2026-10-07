import { describe, expect, it } from "vitest";

import { recognizePage } from "../src/adapters";
import { eamisObservationToRawRows, parseEamisCellEntries } from "../src/eamis";
import { parseObservation } from "../src/parse";
import { parseWeeks } from "../src/weeks";
import type { PageObservation, TermCalendar } from "../src/types";

/**
 * B08 eamis 适配器测试。全部样例为匿名化虚构数据，
 * 真实课程名/教师名不进仓库（核查纪律，docs/evidence/B/adapter-observation.md）。
 */

const term: TermCalendar = {
  term_id: "anon-term",
  timezone: "Asia/Shanghai",
  week1_monday: "2026-08-31",
  teaching_weeks: 17,
  calendar_status: "demo",
  periods: Array.from({ length: 14 }, (_, i) => ({
    period: i + 1,
    start: "08:00",
    end: "08:45",
  })),
  overrides: [],
  source_ref: "匿名化测试校历",
};

function eamisObservation(rows: string[][]): PageObservation {
  return {
    origin: "https://eamis.nankai.edu.cn",
    pathname: "/eams/courseTableForStd!courseTable.action",
    frameOrigin: null,
    tableHeaders: ["课程条目", "星期", "节次"],
    rows,
    selectedTerm: "2026-2027-1",
    selectedWeeks: [],
    hasPagination: false,
    hasVirtualRows: false,
  };
}

describe("B08 周次前缀单双写法", () => {
  it("双2-16 解析为偶数周", () => {
    expect(parseWeeks("双2-16").weeks).toEqual([2, 4, 6, 8, 10, 12, 14, 16]);
  });
  it("单1-15 解析为奇数周", () => {
    expect(parseWeeks("单1-15").weeks).toEqual([1, 3, 5, 7, 9, 11, 13, 15]);
  });
  it("多段周次 1-4 6-17 保持可用", () => {
    const weeks = parseWeeks("1-4 6-17").weeks;
    expect(weeks?.[0]).toBe(1);
    expect(weeks?.includes(5)).toBe(false);
    expect(weeks?.length).toBe(16);
  });
});

describe("B08 单元格条目切分", () => {
  it("单条目：名称(序号) (教师)(周次,地点)", () => {
    const { entries, residue } = parseEamisCellEntries("示例课程甲(0001) (某甲)(1-17,示例楼A区101)");
    expect(residue).toBeNull();
    expect(entries).toEqual([
      { title: "示例课程甲", sequence: "0001", teacher: "某甲", weeksAndLocation: "1-17,示例楼A区101" },
    ]);
  });

  it("课程名含全角括号不被误切", () => {
    const { entries, residue } = parseEamisCellEntries("示例课程（上册）(0002) (某乙)(9-16,示例楼B区115)");
    expect(residue).toBeNull();
    expect(entries[0].title).toBe("示例课程（上册）");
  });

  it("停课条目 + 正常条目拼接切开", () => {
    const { entries, residue } = parseEamisCellEntries(
      "示例课程乙(0003) (某丙)(5,停课)示例课程乙(0003) (某丙)(1-4 6-17,示例楼C区530)",
    );
    expect(residue).toBeNull();
    expect(entries.length).toBe(2);
    expect(entries[0].weeksAndLocation).toBe("5,停课");
    expect(entries[1].weeksAndLocation).toBe("1-4 6-17,示例楼C区530");
  });

  it("无法解析的残留文本如实上报", () => {
    const { residue } = parseEamisCellEntries("示例课程丙(0004) (某丁)(1-2,示例楼)多余尾巴");
    expect(residue).toBe("多余尾巴");
  });
});

describe("B08 观察值转换与整链路", () => {
  it("识别 eamis origin + path + 提取契约表头", () => {
    const recognition = recognizePage(
      eamisObservation([["示例课程甲(0001) (某甲)(1-17,示例楼A区101)", "星期一", "1-2"]]),
    );
    expect(recognition.supported).toBe(true);
    expect(recognition.adapterId).toBe("nku-adapter-v1");
  });

  it("rowSpan 展开后的跨节条目解析为一个 meeting", () => {
    const result = parseObservation(
      eamisObservation([["示例课程甲(0001) (某甲)(1-17,示例楼A区101)", "星期一", "1-2"]]),
      term,
      { capturedAt: "2026-10-07T18:00:00+08:00" },
    );
    expect(result.payload).not.toBeNull();
    const course = result.payload!.courses[0];
    expect(course.title).toBe("示例课程甲");
    expect(course.teacher_display).toBe("某甲");
    expect(course.meetings.length).toBe(1);
    expect(course.meetings[0].weekday).toBe(1);
    expect(course.meetings[0].start_period).toBe(1);
    expect(course.meetings[0].end_period).toBe(2);
    expect(course.meetings[0].weeks.length).toBe(17);
    // 学分网格里没有，必须保持 null 并出现在缺失字段提示中
    expect(course.credits).toBeNull();
    expect(result.issues.some((issue) => issue.code === "missing_fields")).toBe(true);
  });

  it("停课条目不产出 meeting，记录非阻塞提示", () => {
    const result = parseObservation(
      eamisObservation([
        ["示例课程乙(0003) (某丙)(5,停课)示例课程乙(0003) (某丙)(1-4 6-17,示例楼C区530)", "星期二", "6-8"],
      ]),
      term,
      { capturedAt: "2026-10-07T18:00:00+08:00" },
    );
    expect(result.payload).not.toBeNull();
    const meetings = result.payload!.courses[0].meetings;
    expect(meetings.length).toBe(1);
    expect(meetings[0].weeks.includes(5)).toBe(false);
    const cancel = result.issues.find((issue) => issue.code === "cancelled_meeting");
    expect(cancel).toBeDefined();
    expect(cancel!.blocking).toBe(false);
  });

  it("双周前缀 + 多教师 + 多地点保留原文", () => {
    const result = parseObservation(
      eamisObservation([
        ["示例课程丁(0005) (某戊,某己)(双2-16,示例楼B区423)", "星期四", "11-13"],
      ]),
      term,
      { capturedAt: "2026-10-07T18:00:00+08:00" },
    );
    const meetings = result.payload!.courses[0].meetings;
    expect(meetings[0].weeks).toEqual([2, 4, 6, 8, 10, 12, 14, 16]);
    expect(result.payload!.courses[0].teacher_display).toBe("某戊,某己");
  });

  it("残留文本 blocking，绝不产出半解析课表", () => {
    const result = parseObservation(
      eamisObservation([["???乱码(0006) (某庚)(1-2,示例楼)@@@", "星期一", "1-2"]]),
      term,
    );
    expect(result.payload).toBeNull();
    expect(result.issues.some((issue) => issue.blocking)).toBe(true);
  });

  it("学分缺失不阻塞：payload 的 coverage 为 term/complete", () => {
    const result = parseObservation(
      eamisObservation([["示例课程甲(0001) (某甲)(1-17,示例楼A区101)", "星期一", "1-2"]]),
      term,
      { capturedAt: "2026-10-07T18:00:00+08:00" },
    );
    expect(result.payload!.source.coverage).toEqual({
      scope: "term",
      week_numbers: Array.from({ length: 17 }, (_, i) => i + 1),
      completeness: "complete",
    });
  });
});
