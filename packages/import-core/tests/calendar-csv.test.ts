import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { actualDateFor, getEffectiveTemplate, shanghaiIsoNow } from "../src/calendar";
import { parseImportFile } from "../src/parse";
import type { TermCalendar } from "../src/types";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const term = JSON.parse(
  readFileSync(resolve(repoRoot, "fixtures/term.demo.json"), "utf-8"),
) as TermCalendar;

describe("调休模板映射（与后端 expand_occurrences 同语义）", () => {
  it("actualDateFor：第 3 周周一是 2026-09-21", () => {
    expect(actualDateFor(term, 1, 1)).toBe("2026-09-07");
    expect(actualDateFor(term, 3, 1)).toBe("2026-09-21");
    expect(actualDateFor(term, 3, 7)).toBe("2026-09-27");
  });

  it("无 override 时返回原模板", () => {
    expect(getEffectiveTemplate(term, "2026-09-21", 3, 1)).toEqual({
      week: 3,
      weekday: 1,
      overridden: false,
      sourceRef: null,
    });
  });

  it("replace：改用替换模板，不与原模板叠加（TIME-08）", () => {
    const withOverride: TermCalendar = {
      ...term,
      overrides: [
        {
          date: "2026-09-21",
          action: "replace",
          teaching_week: 3,
          weekday: 2,
          source_ref: "虚构调休通知",
        },
      ],
    };
    expect(getEffectiveTemplate(withOverride, "2026-09-21", 3, 1)).toEqual({
      week: 3,
      weekday: 2,
      overridden: true,
      sourceRef: "虚构调休通知",
    });
    // 被替换模板原来的日期（周二）保持自己的模板
    expect(getEffectiveTemplate(withOverride, "2026-09-22", 3, 2)?.weekday).toBe(2);
  });

  it("cancel：当日无课程", () => {
    const withOverride: TermCalendar = {
      ...term,
      overrides: [
        {
          date: "2026-09-21",
          action: "cancel",
          teaching_week: null,
          weekday: null,
          source_ref: "虚构停课通知",
        },
      ],
    };
    expect(getEffectiveTemplate(withOverride, "2026-09-21", 3, 1)).toBeNull();
  });
});

describe("时间输出约定（PR #2 审核意见 6）", () => {
  it("shanghaiIsoNow 输出 +08:00 偏移而不是 Z", () => {
    const iso = shanghaiIsoNow(new Date("2026-09-19T04:00:00Z"));
    expect(iso).toBe("2026-09-19T12:00:00+08:00");
    expect(iso.endsWith("Z")).toBe(false);
  });

  it("文件导入默认 captured_at 使用 +08:00", () => {
    const csv = ["课程,星期,节次,周次", "数学（虚构）,周一,1-2,1-4"].join("\n");
    const result = parseImportFile({ name: "a.csv", content: csv }, "csv", term);
    expect(result.payload!.source.captured_at).toMatch(/\+08:00$/);
  });
});

describe("CSV 引号内换行（PR #2 审核意见 6）", () => {
  it("引号内带换行和逗号的字段被完整解析", () => {
    const csv = [
      "课程,星期,节次,周次,地点",
      '"跨行\n课程（虚构）,含逗号",周一,1-2,1-4,"示例楼\n101"',
    ].join("\n");
    const result = parseImportFile({ name: "quoted.csv", content: csv }, "csv", term);
    expect(result.payload).not.toBeNull();
    expect(result.payload!.courses[0].title).toBe("跨行\n课程（虚构）,含逗号");
    expect(result.payload!.courses[0].meetings[0].location).toBe("示例楼\n101");
  });

  it("双引号转义", () => {
    const csv = ["课程,星期,节次,周次", '"课程""甲""（虚构）",周一,1-2,1-4'].join("\n");
    const result = parseImportFile({ name: "q.csv", content: csv }, "csv", term);
    expect(result.payload!.courses[0].title).toBe('课程"甲"（虚构）');
  });
});

describe("观察值导出→导入闭环（PR #2 复审 P2）", () => {
  it("扩展导出的 PageObservation JSON 可在关联日历后重新导入", () => {
    const observation = {
      origin: "https://fixtures.example.invalid",
      pathname: "/demo/timetable",
      frameOrigin: null,
      tableHeaders: ["课程", "星期", "节次", "周次", "地点"],
      rows: [["高等数学（虚构）", "周一", "1-2", "1-4", "示例楼101"]],
      selectedTerm: "demo-term-2026A",
      selectedWeeks: [],
      hasPagination: false,
      hasVirtualRows: false,
    };
    const result = parseImportFile(
      { name: "observation-export.json", content: JSON.stringify(observation) },
      "json",
      term,
      { datasetKind: "demo", capturedAt: "2026-09-19T12:00:00+08:00" },
    );
    expect(result.payload).not.toBeNull();
    expect(result.payload!.courses[0].title).toBe("高等数学（虚构）");
    expect(result.payload!.source.kind).toBe("visible_dom");
    expect(result.payload!.source.adapter_id).toBe("demo-fixture-adapter");
  });

  it("导出的标准 TimetableImport 仍可回导（两种导出格式都能闭环）", () => {
    const standard = JSON.parse(
      readFileSync(resolve(repoRoot, "fixtures/timetable.demo.json"), "utf-8"),
    );
    const result = parseImportFile(
      { name: "timetable.json", content: JSON.stringify(standard) },
      "json",
      term,
    );
    expect(result.payload).not.toBeNull();
    expect(result.payload!.courses).toHaveLength(3);
  });
});
