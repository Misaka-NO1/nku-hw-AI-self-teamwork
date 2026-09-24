/**
 * CAMPUS-01/02/03：无正式来源不编造流程；校区/人群规则不混用；过期给出提示。
 */
import { describe, expect, it } from "vitest";
import {
  entryDisplayState,
  entrySources,
  filterAffairs,
  listAffairs,
} from "./data";
import type { AffairEntry } from "./types";

const baseEntry: AffairEntry = {
  entryId: "t-entry",
  kind: "entry",
  title: "测试入口",
  category: "academic",
  campusScope: [],
  audience: [],
  officialUrl: null,
  loginRequired: "unknown",
  campusNetworkRequired: "unknown",
  steps: [],
  requiredMaterials: [],
  sourceRefs: [],
  verifiedAt: null,
  validUntil: null,
  status: "needs_verification",
};

describe("CAMPUS-01 无正式来源不编造", () => {
  it("无来源且无核验时间的条目一律是待核验", () => {
    for (const entry of listAffairs()) {
      const hasSource = entry.sourceRefs.length > 0 || entry.officialUrl !== null;
      if (!hasSource || !entry.verifiedAt) {
        expect(entryDisplayState(entry)).toBe("needs_verification");
      }
    }
  });

  it("数据集中不存在伪装成 verified 的无来源条目", () => {
    const offenders = listAffairs().filter(
      (e) =>
        e.status === "verified" &&
        (!e.verifiedAt || (e.sourceRefs.length === 0 && e.officialUrl === null))
    );
    expect(offenders).toEqual([]);
  });
});

describe("CAMPUS-02 校区/人群规则不混用", () => {
  it("按八里台筛选时排除仅津南的条目", () => {
    const result = filterAffairs(listAffairs(), { campus: "八里台" });
    expect(result.length).toBeGreaterThan(0);
    for (const entry of result) {
      if (entry.campusScope.length > 0) {
        expect(entry.campusScope).toContain("八里台");
      }
    }
    const ids = result.map((e) => e.entryId);
    expect(ids).not.toContain("demo-proc-03"); // 仅津南
    expect(ids).not.toContain("demo-entry-08"); // 仅津南
  });

  it("按津南筛选时排除仅八里台的条目", () => {
    const result = filterAffairs(listAffairs(), { campus: "津南" });
    const ids = result.map((e) => e.entryId);
    expect(ids).not.toContain("demo-proc-05"); // 仅八里台
  });
});

describe("CAMPUS-03 过期规则提示", () => {
  it("显式 expired 或 valid_until 早于今天都判定过期", () => {
    const expired = listAffairs().find((e) => e.entryId === "demo-proc-05")!;
    expect(entryDisplayState(expired, "2026-09-22")).toBe("expired");
    // 来源时间保留，供页面展示
    expect(expired.verifiedAt).toBe("2025-03-01");
    expect(expired.validUntil).toBe("2025-09-01");
  });
});

describe("分类搜索", () => {
  it("按分类与关键词过滤", () => {
    const byCategory = filterAffairs(listAffairs(), { category: "academic" });
    expect(byCategory.every((e) => e.category === "academic")).toBe(true);
    const byQuery = filterAffairs(listAffairs(), { query: "报修" });
    expect(byQuery.map((e) => e.entryId)).toContain("demo-proc-03");
  });
});

describe("officialUrl 展示与来源判断一致（PR #3 审核回归）", () => {
  it("officialUrl 有值且已核验时，来源列表含正式入口且状态为 verified", () => {
    const entry: AffairEntry = {
      ...baseEntry,
      officialUrl: "https://example.edu.cn/official-entry",
      verifiedAt: "2026-09-01",
      status: "verified",
    };
    expect(entryDisplayState(entry)).toBe("verified");
    const sources = entrySources(entry);
    expect(sources.length).toBe(1);
    expect(sources[0].href).toBe("https://example.edu.cn/official-entry");
  });

  it("officialUrl 与 sourceRefs 都为空时才提示暂无正式来源", () => {
    expect(entrySources(baseEntry)).toEqual([]);
    expect(entryDisplayState(baseEntry)).toBe("needs_verification");
  });
});
