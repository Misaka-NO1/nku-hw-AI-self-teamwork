import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
describe("培养计划独立注入边界", () => {
  it("仅在计划完成情况页注入培养计划脚本，不扩大到整个教务站", () => {
    const entry = manifest.content_scripts.find((item: { js: string[] }) => item.js.includes("dist/degree-content.js"));
    expect(entry.matches).toEqual(["https://eamis.nankai.edu.cn/eams/myPlanCompl.action"]);
    expect(manifest.host_permissions).not.toContain("https://eamis.nankai.edu.cn/*");
  });
  it("保留原课表页脚本及原核对页桥接", () => {
    const timetable = manifest.content_scripts.find((item: { js: string[] }) => item.js.includes("dist/content.js"));
    expect(timetable.matches).toEqual(["https://eamis.nankai.edu.cn/eams/courseTableForStd*"]);
    const bridge = manifest.content_scripts.find((item: { js: string[] }) => item.js.includes("dist/app-bridge.js"));
    expect(bridge.matches.every((url: string) => url.endsWith("/tools/import*"))).toBe(true);
    expect(bridge.js).toEqual(["dist/app-bridge.js"]);
  });
});
