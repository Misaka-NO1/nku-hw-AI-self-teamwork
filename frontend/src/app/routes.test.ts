/**
 * SHELL-01：所有 /tools/* 路径可刷新——路由表对每个工具路径都有
 * 对应页面组件或明确占位，不落服务器默认 404。
 */
import { describe, expect, it } from "vitest";
import { TOOL_NAV, toolNavHref } from "./nav";
import * as pages from "./pages";

describe("SHELL-01 路由与页面导出", () => {
  it("导航只显示课表、地图、待办日历", () => {
    expect(TOOL_NAV.map((n) => n.path)).toEqual(["/tools/timetable", "/tools/map", "/tools/calendar"]);
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
      "CalendarPage",
    ]) {
      expect(typeof (pages as Record<string, unknown>)[name]).toBe("function");
    }
  });

  it("公开地图链接到身份服务的课表，而非本站不存在的课表路径", () => {
    expect(toolNavHref("/tools/timetable", {publicContentOnly: true, identityPilot: false,
      timetableOrigin: "https://identity.example/tools/login?ignored=1"})).toBe("https://identity.example/tools/timetable");
  });

  it("身份服务链接到公开地图，本地完整开发保持相对链接", () => {
    expect(toolNavHref("/tools/map", {publicContentOnly: false, identityPilot: true,
      publicContentOrigin: "https://content.example/"})).toBe("https://content.example/tools/map");
    expect(toolNavHref("/tools/map", {publicContentOnly: false, identityPilot: false})).toBe("/tools/map");
  });

  it("缺少或非法跨站配置时禁用入口，不生成错误链接", () => {
    for (const timetableOrigin of [undefined, "javascript:alert(1)", "https://user:secret@example.com"]) {
      expect(toolNavHref("/tools/timetable", {publicContentOnly: true, identityPilot: false, timetableOrigin})).toBeUndefined();
    }
  });
  it("公开服务的日历也链接到身份服务", () => {
    expect(toolNavHref("/tools/calendar", {publicContentOnly:true, identityPilot:false,
      timetableOrigin:"https://identity.example"})).toBe("https://identity.example/tools/calendar");
    expect(toolNavHref("/tools/calendar", {publicContentOnly:true, identityPilot:false})).toBeUndefined();
  });
});
