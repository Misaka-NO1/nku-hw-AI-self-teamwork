/**
 * CAMPUS-01/02/03：无正式来源不编造流程；校区/人群规则不混用；过期给出提示。
 */
import { describe, expect, it } from "vitest";
import {
  entryDisplayState,
  entrySources,
  filterAffairs,
  findAffairGuides,
  listAffairs,
} from "./data";
import type { AffairEntry } from "./types";
import demoFixtures from "../../../../knowledge/affairs/fixtures.demo.json";
import { snakeToCamel } from "../../shared/api/convert";

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
    expect(ids).not.toContain("demo-proc-06"); // 仅津南
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
    const expired = snakeToCamel(demoFixtures.entries.find((e) => e.entry_id === "demo-proc-05")) as unknown as AffairEntry;
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
    expect(byQuery.map((e) => e.entryId)).toContain("nku-proc-dorm-repair");
  });
});

describe("自然语言办事指南", () => {
  it("支持掉卡口语问法，补办学生证仍走原流程", () => {
    expect(findAffairGuides("一卡通掉了怎么办？")[0].entryId).toBe("nku-proc-card-help");
    expect(findAffairGuides("补办学生证要带什么材料？")[0].entryId).toBe("nku-proc-student-card");
  });
  it("宿舍一般漏水与空调漏水分别匹配，显式研究生仍不套本科流程", () => {
    expect(findAffairGuides("宿舍漏水找谁修？")[0].entryId).toBe("nku-proc-dorm-repair");
    expect(findAffairGuides("宿舍空调漏水怎么办？")[0].entryId).toBe("nku-proc-airconditioner-repair");
    expect(findAffairGuides("研究生学生证丢了怎么补？")).toEqual([]);
  });
  it("图书馆预约只给已收录入口，不借用体育场馆流程", () => {
    const guide = findAffairGuides("图书馆怎么预约座位？")[0];
    expect(guide.entryId).toBe("nku-entry-04");
    expect(guide.steps).toEqual([]);
    expect(guide.officialUrl).toBe("https://libroom.nankai.edu.cn/");
    expect(findAffairGuides("电费在哪交？")[0].status).toBe("verified");
    expect(findAffairGuides("电费在哪交？")[0].verifiedAt).toBe("2026-10-09");
    expect(findAffairGuides("电费在哪交？")[0].steps.join(" ")).toContain("绑定房间");
  });
  it("学生证与校园卡丢失使用不同受理指南", () => {
    expect(findAffairGuides("我的学生证丢了怎么补办？")[0].entryId).toBe("nku-proc-student-card");
    expect(findAffairGuides("校园卡丢了怎么办？")[0].entryId).toBe("nku-proc-card-help");
  });
  it("空调故障匹配官方步骤与来源，租赁优先匹配租赁流程", () => {
    const repair = findAffairGuides("宿舍空调不制冷怎么办？")[0];
    expect(repair.entryId).toBe("nku-proc-airconditioner-repair");
    expect(repair.steps.join(" ")).toContain("我的报修");
    expect(repair.officialUrl).toBe("https://hq.nankai.edu.cn/24032/listm.htm");
    expect(findAffairGuides("我要申请空调租赁")[0].entryId).toBe("nku-proc-airconditioner-rental");
  });
  it("不把待核验指引洗成规定，不回答未收录与不适用的流程", () => {
    expect(findAffairGuides("校园卡充值指引")[0].status).toBe("needs_verification");
    expect(findAffairGuides("研究生成绩单怎么打印？")).toEqual([]);
    expect(findAffairGuides("如何申请火星通行证？")).toEqual([]);
    expect(listAffairs().some((entry) => entry.entryId.startsWith("demo-"))).toBe(false);
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
