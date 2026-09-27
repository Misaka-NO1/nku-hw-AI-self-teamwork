import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { recognizePage } from "../src/adapters";
import { normalizeCourses } from "../src/normalize";
import { parseImportFile, tableToRawRows } from "../src/parse";
import type { PageObservation, TermCalendar } from "../src/types";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const term = JSON.parse(
  readFileSync(resolve(repoRoot, "fixtures/term.demo.json"), "utf-8"),
) as TermCalendar;
const timetableFixture = JSON.parse(
  readFileSync(resolve(repoRoot, "fixtures/timetable.demo.json"), "utf-8"),
);

const HEADERS = ["课程", "星期", "节次", "周次", "地点"];

function demoObservation(overrides: Partial<PageObservation> = {}): PageObservation {
  return {
    origin: "https://fixtures.example.invalid",
    pathname: "/demo/timetable",
    frameOrigin: null,
    tableHeaders: HEADERS,
    rows: [
      ["高等数学（虚构）", "周一", "1-2", "1-4", "示例楼101"],
      ["高等数学（虚构）", "周三", "3-4", "1-4", "示例楼101"],
    ],
    selectedTerm: "demo-term-2026A",
    selectedWeeks: [],
    hasPagination: false,
    hasVirtualRows: false,
    ...overrides,
  };
}

describe("IMPORT-01 空页/登录页/未知表头拒绝导入", () => {
  it("空数据行拒绝导入", () => {
    const recognition = recognizePage(demoObservation({ rows: [] }));
    expect(recognition.supported).toBe(false);
    expect(recognition.reason).toContain("UNSUPPORTED_PAGE");
  });

  it("未知表头拒绝导入", () => {
    const recognition = recognizePage(demoObservation({ tableHeaders: ["账号", "密码"] }));
    expect(recognition.supported).toBe(false);
    expect(recognition.reason).toContain("UNSUPPORTED_PAGE");
  });

  it("tableToRawRows 遇到未知表头返回 null", () => {
    expect(tableToRawRows(["学号", "姓名"], [["1", "张三"]])).toBeNull();
  });

  it("非白名单域名拒绝（EXT-01 前置）", () => {
    const recognition = recognizePage(demoObservation({ origin: "https://evil.example.com" }));
    expect(recognition.supported).toBe(false);
    expect(recognition.reason).toContain("非白名单");
  });

  it("nku-adapter-v1 在真实核查前保持 disabled，不猜域名", () => {
    const recognition = recognizePage(
      demoObservation({ origin: "https://eamis.nankai.edu.cn", pathname: "/demo/timetable" }),
    );
    expect(recognition.supported).toBe(false);
  });
});

describe("IMPORT-02 同课程不同 meeting 都保留", () => {
  it("同一 course_id 的多个 meeting 不误删", () => {
    const rows = tableToRawRows(HEADERS, [
      ["程序设计（虚构）", "周一", "1-2", "1-4", "示例楼101"],
      ["程序设计（虚构）", "周三", "5-6", "1-4", "示例楼202"],
      ["程序设计实验（虚构）", "周二", "5-6", "1-4", "示例楼303"],
    ]);
    expect(rows).not.toBeNull();
    const result = normalizeCourses(rows!, {
      calendar: term,
      kind: "fixture",
      adapterId: "demo-fixture-adapter",
      adapterVersion: "1.0.0",
      capturedAt: "2026-09-19T12:00:00+08:00",
      datasetKind: "demo",
      completenessHint: "complete",
    });
    expect(result.payload).not.toBeNull();
    const titles = result.payload!.courses.map((course) => course.title);
    expect(titles).toContain("程序设计（虚构）");
    expect(titles).toContain("程序设计实验（虚构）");
  });

  it("完全重复的 meeting 只保留一条并记录 issue", () => {
    const rows = tableToRawRows(HEADERS, [
      ["程序设计（虚构）", "周一", "1-2", "1-4", "示例楼101"],
      ["程序设计（虚构）", "周一", "1-2", "1-4", "示例楼101"],
    ])!;
    rows[1].courseId = rows[0].courseId; // 同课程
    rows[0].courseId = "demo-X";
    rows[1].courseId = "demo-X";
    const result = normalizeCourses(rows, {
      calendar: term,
      kind: "fixture",
      adapterId: "demo-fixture-adapter",
      adapterVersion: "1.0.0",
      capturedAt: "2026-09-19T12:00:00+08:00",
      datasetKind: "demo",
      completenessHint: "complete",
    });
    expect(result.payload!.courses[0].meetings).toHaveLength(1);
    expect(result.issues.some((issue) => issue.code === "duplicate_meeting")).toBe(true);
  });
});

describe("标准 JSON 导入", () => {
  it("fixtures/timetable.demo.json 通过结构与语义规范化", () => {
    const result = parseImportFile(
      { name: "timetable.demo.json", content: JSON.stringify(timetableFixture) },
      "json",
      term,
      { datasetKind: "demo", capturedAt: "2026-09-19T12:00:00+08:00" },
    );
    expect(result.payload).not.toBeNull();
    expect(result.payload!.source.coverage.completeness).toBe("complete");
  });

  it("空课程 JSON 拒绝导入空课表", () => {
    const result = parseImportFile(
      { name: "empty.json", content: JSON.stringify({ courses: [] }) },
      "json",
      term,
    );
    expect(result.payload).toBeNull();
    expect(result.issues.some((issue) => issue.code === "empty_timetable")).toBe(true);
  });

  it("写入标准 JSON 使用 snake_case 的 adapter_id/adapter_version", () => {
    const result = parseImportFile(
      { name: "timetable.demo.json", content: JSON.stringify(timetableFixture) },
      "json",
      term,
    );
    expect(result.payload!.source.adapter_id).toBe("demo-adapter");
    expect(result.payload!.source).not.toHaveProperty("adapterId");
  });
});

describe("规范 CSV 导入", () => {
  it("解析标准 CSV 并保留覆盖范围提示（TIME-07 partial）", () => {
    const csv = [
      "课程,星期,节次,周次,地点",
      "高等数学（虚构）,周一,1-2,1-4,示例楼101",
      "大学物理（虚构）,周二,3-4,1-2,示例楼102",
    ].join("\n");
    const result = parseImportFile({ name: "timetable.csv", content: csv }, "csv", term, {
      datasetKind: "demo",
      capturedAt: "2026-09-19T12:00:00+08:00",
    });
    expect(result.payload).not.toBeNull();
    expect(result.payload!.courses).toHaveLength(2);
    expect(result.payload!.source.coverage.scope).toBe("term");
    // 文件导入无法证明覆盖全学期，completeness 不能自称 complete
    expect(result.payload!.source.coverage.completeness).toBe("unknown");
  });

  it("非法周次在导入时即被拦截", () => {
    const csv = ["课程,星期,节次,周次", "高等数学（虚构）,周一,1-2,abc"].join("\n");
    const result = parseImportFile({ name: "bad.csv", content: csv }, "csv", term);
    expect(result.payload).toBeNull();
    expect(result.issues.some((issue) => issue.code === "invalid_weeks")).toBe(true);
  });

  it("超过行数上限报错", () => {
    const csv = ["课程,星期,节次,周次", ...Array.from({ length: 2001 }, () => "x,1,1,1")].join("\n");
    const result = parseImportFile({ name: "big.csv", content: csv }, "csv", term);
    expect(result.payload).toBeNull();
    expect(result.issues[0].code).toBe("file_too_large");
  });
});
