/** Explicit development-only HTML entry. Never imported by the production app. */
import { createRoot } from "react-dom/client";
import { DegreeReadPreview } from "./DegreeReadPreview";
import { extractDegreeTable } from "../../../../packages/import-core/src/degree-page";

function QA() {
  function read() {
    const table = document.querySelector<HTMLTableElement>("#anonymous-source")!;
    const observation = extractDegreeTable(table, "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", new Date().toISOString());
    window.dispatchEvent(new CustomEvent("campus:degree-observation", { detail: observation }));
  }
  return <main style={{ maxWidth: 1200, margin: "24px auto", padding: 20, fontFamily: "sans-serif" }}>
    <h1>第6模块本地匿名验收</h1>
    <p>以下全部是虚构测试数据。本页仅验证本地提取、核对和后端分析，不代表学校页面或插件已接通。</p>
    <details><summary>查看匿名源表格</summary>
      <table id="anonymous-source"><thead><tr>{["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"].map(value => <th key={value}>{value}</th>)}</tr></thead>
        <tbody>
          <tr><td colSpan={3}>1 虚构总模块（所有子项满足）</td><td>6</td><td>4</td><td></td><td>缺2学分缺1门</td><td></td></tr>
          <tr><td colSpan={3}>1.1 虚构专业基础（所有子项满足）</td><td>4</td><td>4</td><td></td><td>是</td><td></td></tr>
          <tr><td>1</td><td>ANON101</td><td>虚构通过课程</td><td>2</td><td>2</td><td>88</td><td>是</td><td>必修</td></tr>
          <tr><td>2</td><td>ANON102</td><td>虚构在读课程</td><td>2</td><td>2</td><td>--</td><td>是</td><td>在读 必修</td></tr>
          <tr><td colSpan={3}>1.2 虚构拓展模块</td><td>2</td><td>0</td><td></td><td>缺2学分缺1门</td><td></td></tr>
          <tr><td>1</td><td>ANON201</td><td>虚构待认定课程</td><td>2</td><td>0</td><td>--</td><td>是</td><td>待认定</td></tr>
        </tbody></table>
    </details>
    <button onClick={read}>主动读取匿名测试表格</button>
    <DegreeReadPreview />
  </main>;
}
createRoot(document.getElementById("root")!).render(<QA />);
