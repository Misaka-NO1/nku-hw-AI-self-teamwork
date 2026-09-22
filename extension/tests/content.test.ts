// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import { extractCourseObservation, UnsupportedPageError } from "../src/content";

describe("EXT-03 页面结构变化/登录页给出明确降级", () => {
  it("页面改版缺少必需表头时抛出 UNSUPPORTED_PAGE 并提示文件导入", () => {
    const doc = new DOMParser().parseFromString(
      `<html><body><table><tr><td>全新</td><td>布局</td></tr></table></body></html>`,
      "text/html",
    );
    expect(() => extractCourseObservation(doc, { pageUrl: "https://fixtures.example.invalid/demo/timetable" })).toThrowError(UnsupportedPageError);
    try {
      extractCourseObservation(doc, { pageUrl: "https://fixtures.example.invalid/demo/timetable" });
    } catch (error) {
      expect((error as UnsupportedPageError).code).toBe("UNSUPPORTED_PAGE");
      expect((error as UnsupportedPageError).fallback).toContain("文件导入");
    }
  });

  it("登录页（密码框、无课程表）拒绝读取", () => {
    const doc = new DOMParser().parseFromString(
      `<html><body><form><input type="password" name="pwd"></form></body></html>`,
      "text/html",
    );
    expect(() => extractCourseObservation(doc, { pageUrl: "https://fixtures.example.invalid/demo/timetable" })).toThrowError(/UNSUPPORTED_PAGE/);
  });

  it("正常课程表只提取白名单文本字段", () => {
    const doc = new DOMParser().parseFromString(
      `<html><body>
        <table>
          <tr><th>课程</th><th>星期</th><th>节次</th><th>周次</th></tr>
          <tr><td>高等数学（虚构）</td><td>周一</td><td>1-2</td><td>1-4</td></tr>
        </table>
      </body></html>`,
      "text/html",
    );
    const observation = extractCourseObservation(doc, { pageUrl: "https://fixtures.example.invalid/demo/timetable" });
    expect(observation.tableHeaders).toEqual(["课程", "星期", "节次", "周次"]);
    expect(observation.rows).toEqual([["高等数学（虚构）", "周一", "1-2", "1-4"]]);
    // 观察值不包含任何 cookie/认证字段
    expect(JSON.stringify(observation)).not.toContain("cookie");
  });
});
