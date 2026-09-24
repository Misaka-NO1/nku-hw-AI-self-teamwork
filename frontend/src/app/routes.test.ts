/**
 * SHELL-01：所有 /tools/* 路径可刷新——路由表对每个工具路径都有
 * 对应页面组件或明确占位，不落服务器默认 404。
 */
import { describe, expect, it } from "vitest";
import { TOOL_NAV } from "./nav";
import * as pages from "./pages";

const EXPECTED_PATHS = [
  "/tools/import",
  "/tools/timetable",
  "/tools/tasks",
  "/tools/map",
  "/tools/study",
  "/tools/affairs",
  "/tools/degree",
];

describe("SHELL-01 路由与页面导出", () => {
  it("导航表覆盖全部 7 个契约路径", () => {
    expect(TOOL_NAV.map((n) => n.path).sort()).toEqual([...EXPECTED_PATHS].sort());
  });

  it("统一导出 7 个页面组件", () => {
    for (const name of [
      "ImportPage",
      "TimetablePage",
      "TasksPage",
      "ScenicPage",
      "StudyPage",
      "AffairsPage",
      "DegreePage",
    ]) {
      expect(typeof (pages as Record<string, unknown>)[name]).toBe("function");
    }
  });
});
