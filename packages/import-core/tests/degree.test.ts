// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { DEGREE_PLAN_URL, degreePlanWarnings, extractDegreePlanFromDoc, parseDegreePlanFile, validateDegreePlanImport } from "../src/degree";
// Synthetic values; structural spans match the observed completion page, no personal records.
const html = `<input name="studentId" value="private-student"><input name="token" value="private-token">
<table><tr><td>学号:</td><td>private-id</td><td>姓名:</td><td>private-name</td><td>年级:</td><td>2025</td></tr>
<tr><td>专业/专业方向:</td><td>虚构专业</td><td>要求学分/完成学分/实修学分:</td><td>150 / 12.5 / 15</td></tr>
<tr><td>审核结果:</td><td>未通过 预审，有在读课程</td><td>审核时间:</td><td>2026-10-12 10:00:00</td><td>审核人:</td><td>private-reviewer</td></tr>
<tr><td>备注:</td><td>该完成情况，不作为最终审核结果</td></tr></table>
<table><tr><td>序号</td><td>课程序号</td><td>课程名称</td><td>要求学分</td><td>实修学分</td><td>成绩</td><td>是否通过</td><td>备注</td></tr>
<tr><td colspan="3">一 虚构基础模块(所有子项均应满足要求)</td><td>8</td><td>2.5</td><td></td><td>缺 5.5 学分 缺 2 门</td><td></td></tr>
<tr><td>1</td><td>TEST001</td><td>虚构在读课程</td><td>2.5</td><td>2.5</td><td>--</td><td>是</td><td>在读</td></tr>
<tr><td colspan="3">(一) 虚构子模块</td><td>2</td><td>2</td><td></td><td>是</td><td></td></tr>
<tr><td>1</td><td>TEST002</td><td>虚构已修课程</td><td>2</td><td>2</td><td>通过</td><td>是</td><td></td></tr>
<tr><td>2</td><td>TEST003</td><td>虚构未修课程</td><td>3.5</td><td>0</td><td>--</td><td>否</td><td></td></tr></table>`;
const doc = (s = html) => new DOMParser().parseFromString(s, "text/html");
describe("shared completion report parser", () => {
  it("projects only report fields, preserving grades/pre-audit/in-progress without identity/auth fields", () => {
    const p = extractDegreePlanFromDoc(doc(), DEGREE_PLAN_URL + "?token=private-query");
    expect(p.kind).toBe("degree_completion_snapshot"); expect(p.program).toBe("虚构专业"); expect(p.cohort).toBe("2025");
    expect(p.summary).toEqual({required_credits:"150",completed_credits:"12.5",actual_credits:"15",reported_result:"未通过 预审，有在读课程",reviewed_at:"2026-10-12 10:00:00",note:"该完成情况，不作为最终审核结果"});
    expect(p.rows[0]).toEqual({kind:"module",title:"一 虚构基础模块(所有子项均应满足要求)",required_credits:"8",actual_credits:"2.5",reported_status:"缺 5.5 学分 缺 2 门",note:null});
    expect(p.rows[1]).toEqual({kind:"course",course_code:"TEST001",title:"虚构在读课程",required_credits:"2.5",actual_credits:"2.5",grade:"--",reported_pass:"是",note:"在读"});
    expect(JSON.stringify(p)).not.toContain("private-"); expect(p).not.toHaveProperty("earned_credits");
    expect(degreePlanWarnings(p).join(" ")).toContain("在读");
  });
  it("uses the same bounded projection for inert HTML and BOM JSON files", () => {
    const p = parseDegreePlanFile("completion.html", html + '<script>throw new Error("do not execute")</script>');
    expect(p.rows).toEqual(extractDegreePlanFromDoc(doc(), DEGREE_PLAN_URL).rows);
    expect(p.source).toEqual({kind:"file",origin:null,pathname:null});
    expect(parseDegreePlanFile("completion.json", "\uFEFF"+JSON.stringify(p))).toEqual(p);
  });
  it("refuses login, unknown/empty/inventory, duplicate report tables and unrelated URLs", () => {
    expect(() => extractDegreePlanFromDoc(doc('<input type="password">'+html), DEGREE_PLAN_URL)).toThrow(/登录页/);
    expect(() => extractDegreePlanFromDoc(doc("<table><tr><td>unknown</td></tr></table>"))).toThrow(/未找到唯一/);
    expect(() => extractDegreePlanFromDoc(doc(html+html))).toThrow(/唯一/);
    for (const url of ["https://evil.invalid/report",DEGREE_PLAN_URL+"other","https://eamis.nankai.edu.cn/eams/myPlan!programDoc.action"])
      expect(() => extractDegreePlanFromDoc(doc(),url)).toThrow(/只支持/);
    expect(() => parseDegreePlanFile("plan.pdf", html)).toThrow(/JSON/);
    expect(() => validateDegreePlanImport({...extractDegreePlanFromDoc(doc()),kind:"degree_plan_inventory"})).toThrow(/培养方案清单/);
  });
  it("rejects incomplete header/credit/pass rather than silently skipping rows", () => {
    expect(() => extractDegreePlanFromDoc(doc(html.replace('<td>成绩</td>','<td>未知字段</td>')))).toThrow(/表头/);
    expect(() => extractDegreePlanFromDoc(doc(html.replace('<td>3.5</td>','<td>未知学分</td>')))).toThrow(/学分/);
    expect(() => extractDegreePlanFromDoc(doc(html.replace('<td>否</td>','<td>未知</td>')))).toThrow(/通过状态/);
  });
  it("keeps group policy text and duplicate course allocation without summing or deduplicating", () => {
    const p = extractDegreePlanFromDoc(doc()); p.rows.push({...p.rows[1]});
    expect(validateDegreePlanImport(p).rows).toHaveLength(6);
    expect(degreePlanWarnings(p).join(" ")).toContain("课程代码重复");
    expect(p.rows[0].title).toContain("所有子项均应满足要求");
  });
  it("rejects identity/credential/extra fields, invalid/oversized values", () => {
    const p = extractDegreePlanFromDoc(doc());
    for (const value of [{...p,owner_id:"someone"},{...p,student_id:"someone"},{...p,rows:[{...p.rows[1],token:"secret"}]},
      {...p,rows:[{...p.rows[1],actual_credits:"-1"}]},{...p,rows:[{...p.rows[1],course_code:"姓名"}]},
      {...p,source:{...p.source,origin:"https://evil.invalid"}},{...p,summary:{...p.summary,grade_point:"3.9"}}])
      expect(() => validateDegreePlanImport(value)).toThrow();
    expect(() => parseDegreePlanFile("completion.json", " ".repeat(1024*1024+1))).toThrow(/1 MB/);
  });
  it("does not duplicate nested layout tables or read an unrelated grade table", () => {
    const p = extractDegreePlanFromDoc(doc(`<table><tr><td>${html}</td></tr></table><table><tr><td>成绩</td></tr><tr><td>private-other-grade</td></tr></table>`));
    expect(p.rows).toHaveLength(5); expect(JSON.stringify(p)).not.toContain("private-");
  });
  it("preserves missing summary as unknown, not synthetic totals or final eligibility", () => {
    const p = extractDegreePlanFromDoc(doc(html.slice(html.indexOf('<table><tr><td>序号'))));
    expect(p.summary.completed_credits).toBeNull(); expect(degreePlanWarnings(p).join(" ")).toContain("总览未识别");
  });
  it("handles rowSpan and refuses malformed spans", () => {
    const s = html.replace('<td>TEST002</td>', '<td rowspan="2">TEST002</td>').replace('<td>TEST003</td>', '');
    const p = extractDegreePlanFromDoc(doc(s)); expect(p.rows[4]).toMatchObject({course_code:"TEST002",title:"虚构未修课程"});
    expect(() => extractDegreePlanFromDoc(doc(html.replace('colspan="3"','colspan="40"')))).toThrow(/合并结构/);
  });
});
