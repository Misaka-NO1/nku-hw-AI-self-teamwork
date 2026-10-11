// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { extractDegreeTable, isDegreePage } from "../src/degree-page";

const url = "https://eamis.nankai.edu.cn/eams/myPlanCompl.action";
function table(body: string): HTMLTableElement {
  document.body.innerHTML = `<table><tr><th>课程序号</th><th>课程名称</th><th>要求学分</th><th>实修学分</th><th>成绩</th><th>是否通过</th><th>备注</th></tr>${body}</table>`;
  return document.querySelector("table")!;
}
describe("isolated curriculum table observation", () => {
  it("keeps original module/course text without inferring completion or reading other regions", () => {
    const selected = table('<tr><td colspan="2">虚构模块（所有子项均应满足要求）</td><td>4</td><td>2</td><td></td><td>缺2学分</td></tr><tr><td>TEST001</td><td>虚构课程</td><td>2</td><td>2</td><td>--</td><td>是</td><td>在读</td></tr>');
    document.body.insertAdjacentHTML("beforeend", '<input type="password" value="secret"><div>姓名：某同学 学号：TEST</div>');
    const result = extractDegreeTable(selected, `${url}?student=TEST`, "2026-10-09T08:00:00+08:00");
    expect(result.rows[1].cells).toContain("在读");
    expect(result.rows[0].cells[0]).toContain("所有子项");
    expect(result.source.coverage).toBe("unknown");
    expect(result.source.adapter_verified).toBe(false);
    expect(JSON.stringify(result)).not.toContain("secret");
    expect(result.source.url).toBe(url);
  });
  it("rejects timetable/wrong-host pages and missing headers", () => {
    expect(isDegreePage("https://example.invalid/eams/myPlanCompl.action")).toBe(false);
    const selected = table('<tr><td>TEST</td></tr>');
    expect(() => extractDegreeTable(selected, url.replace("myPlanCompl", "courseTableForStd"), "2026-10-09")).toThrow("UNSUPPORTED");
    selected.deleteRow(0);
    expect(() => extractDegreeTable(selected, url, "2026-10-09")).toThrow("HEADERS");
  });
  it("rejects identity cells and empty results", () => {
    expect(() => extractDegreeTable(table('<tr><td>姓名：虚构</td></tr>'), url, "2026-10-09")).toThrow("IDENTITY");
    expect(() => extractDegreeTable(table(""), url, "2026-10-09")).toThrow("EMPTY");
  });
});
