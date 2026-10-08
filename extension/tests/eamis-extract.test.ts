// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import { extractCourseObservation } from "../src/content";

/**
 * B08 eamis 网格提取测试：匿名化虚构样例，
 * 结构依据 2026-10-07 核查（行=节次 × 列=星期，rowSpan 合并跨节课程）。
 */

const PAGE_URL = "https://eamis.nankai.edu.cn/eams/courseTableForStd!courseTable.action";

function gridDoc(body: string): Document {
  return new DOMParser().parseFromString(`<html><body>${body}</body></html>`, "text/html");
}

describe("B08 eamis 网格提取", () => {
  it("表头校验 + 单节格子输出三列观察值", () => {
    const doc = gridDoc(`
      <table id="manualArrangeCourseTable">
        <tr><th>节次/周次</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th><th>星期六</th><th>星期日</th></tr>
        <tr><th>第一节</th><td>示例课程甲(0001) (某甲)(1-17,示例楼A区101)</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        <tr><th>第二节</th><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
      </table>
    `);
    const observation = extractCourseObservation(doc, { pageUrl: PAGE_URL });
    expect(observation.tableHeaders).toEqual(["课程条目", "星期", "节次"]);
    expect(observation.rows).toEqual([
      ["示例课程甲(0001) (某甲)(1-17,示例楼A区101)", "星期一", "1-1"],
    ]);
    expect(observation.origin).toBe("https://eamis.nankai.edu.cn");
  });

  it("rowSpan=2 的跨节课程只输出一次，节次范围为 1-2", () => {
    const doc = gridDoc(`
      <table id="manualArrangeCourseTable">
        <tr><th>节次/周次</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th><th>星期六</th><th>星期日</th></tr>
        <tr><th>第一节</th><td rowspan="2">示例课程乙(0002) (某乙)(1-9,示例楼B区202)</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        <tr><th>第二节</th><td>示例课程丙(0003) (某丙)(1-9,示例楼C区303)</td><td></td><td></td><td></td><td></td><td></td></tr>
      </table>
    `);
    const observation = extractCourseObservation(doc, { pageUrl: PAGE_URL });
    expect(observation.rows).toEqual([
      ["示例课程乙(0002) (某乙)(1-9,示例楼B区202)", "星期一", "1-2"],
      ["示例课程丙(0003) (某丙)(1-9,示例楼C区303)", "星期二", "2-2"],
    ]);
  });

  it("同格多条目（停课+正常）保持原文拼接，由解析器切分", () => {
    const doc = gridDoc(`
      <table id="manualArrangeCourseTable">
        <tr><th>节次/周次</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th><th>星期六</th><th>星期日</th></tr>
        <tr><th>第六节</th><td></td><td>示例课程丁(0004) (某丁)(5,停课)示例课程丁(0004) (某丁)(1-4 6-17,示例楼C区530)</td><td></td><td></td><td></td><td></td><td></td></tr>
      </table>
    `);
    const observation = extractCourseObservation(doc, { pageUrl: PAGE_URL });
    expect(observation.rows.length).toBe(1);
    expect(observation.rows[0][0]).toContain("停课");
    expect(observation.rows[0][2]).toBe("1-1");
  });

  it("网格存在但表头不符（页面改版）抛 UNSUPPORTED_PAGE", () => {
    const doc = gridDoc(`
      <table id="manualArrangeCourseTable">
        <tr><th>全新</th><th>布局</th></tr>
        <tr><td>x</td><td>y</td></tr>
      </table>
    `);
    expect(() => extractCourseObservation(doc, { pageUrl: PAGE_URL })).toThrowError(/UNSUPPORTED_PAGE/);
  });
});
