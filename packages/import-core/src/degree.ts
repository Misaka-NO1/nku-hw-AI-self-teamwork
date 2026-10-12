/** Projection of the user's visible EAMIS completion report, not a graduation decision.
 * No whole-page HTML, account identifiers, forms, cookies or background requests.
 */
export const DEGREE_PLAN_URL = "https://eamis.nankai.edu.cn/eams/myPlanCompl.action";
export const DEGREE_LIMITS = { bytes: 1024 * 1024, courses: 2000, modules: 200, text: 300 };
export interface DegreePlanCourse {
  kind: "course"; course_code: string; title: string; required_credits: string;
  actual_credits: string; grade: string | null; reported_pass: string | null; note: string | null;
}
export interface DegreePlanModule {
  kind: "module"; title: string; required_credits: string; actual_credits: string;
  reported_status: string | null; note: string | null;
}
export interface DegreePlanImport {
  schema_version: "1.0.0"; kind: "degree_completion_snapshot";
  program: string | null; cohort: string | null;
  source: { kind: "visible_dom" | "file"; origin: string | null; pathname: string | null };
  summary: { required_credits: string | null; completed_credits: string | null; actual_credits: string | null;
    reported_result: string | null; reviewed_at: string | null; note: string | null };
  /** Ordered groups and courses preserve nested policy statements without guessing allocation. */
  rows: Array<DegreePlanCourse | DegreePlanModule>;
}
const clean = (s: string) => s.replace(/\s+/g, " ").trim();
const head = (s: string) => s.replace(/\s/g, "").replace(/：/g, ":");
function fail(s: string): never { throw new Error(s); }
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("计划完成情况 JSON 结构不正确。");
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(k => !keys.includes(k)) || keys.some(k => !(k in row)))
    fail("计划完成情况字段不匹配；不接收姓名、学号、账号、凭据或额外字段。");
  return row;
}
function text(value: unknown, nullable = false): string | null {
  if (nullable && value === null) return null;
  if (typeof value !== "string" || !clean(value) || value.length > DEGREE_LIMITS.text || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value))
    fail("完成情况文本字段缺失或过长。");
  return clean(value as string);
}
function credit(value: unknown, nullable = false): string | null {
  if (nullable && value === null) return null;
  if (typeof value !== "string" || !/^(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?$/.test(value) || Number(value) > 300)
    fail("学分须为 0–300 的非负十进制数（最多两位小数）。");
  return value;
}
export function validateDegreePlanImport(value: unknown): DegreePlanImport {
  if (new TextEncoder().encode(JSON.stringify(value)).length > DEGREE_LIMITS.bytes) fail("计划完成情况文件超过 1 MB。");
  const plan = object(value, ["schema_version", "kind", "program", "cohort", "source", "summary", "rows"]);
  if (plan.schema_version !== "1.0.0" || plan.kind !== "degree_completion_snapshot")
    fail("请选择「计划完成情况」JSON，不是培养方案清单或课表 JSON。");
  const source = object(plan.source, ["kind", "origin", "pathname"]);
  if (!["visible_dom", "file"].includes(String(source.kind))) fail("完成情况来源无效。");
  if ((source.origin !== null || source.pathname !== null) &&
      (source.origin !== "https://eamis.nankai.edu.cn" || source.pathname !== new URL(DEGREE_PLAN_URL).pathname)) fail("完成情况来源不在已支持页面中。");
  const summary = object(plan.summary, ["required_credits", "completed_credits", "actual_credits", "reported_result", "reviewed_at", "note"]);
  if (!Array.isArray(plan.rows) || !plan.rows.length || plan.rows.length > DEGREE_LIMITS.courses + DEGREE_LIMITS.modules)
    fail("未找到完成情况明细，或条数超限；没有导入空报告。");
  const rows = plan.rows.map(value => {
    const kind = value && typeof value === "object" ? (value as Record<string, unknown>).kind : null;
    if (kind === "course") {
      const row = object(value, ["kind", "course_code", "title", "required_credits", "actual_credits", "grade", "reported_pass", "note"]);
      const code = text(row.course_code)!;
      if (!/^[A-Za-z0-9._-]{2,64}$/.test(code)) fail("课程代码无法核实，不能用课程名替代代码。");
      const pass = text(row.reported_pass, true);
      if (pass !== null && !["是", "否"].includes(pass)) fail("课程通过状态未识别，请核对教务原表。");
      return { kind: "course" as const, course_code: code, title: text(row.title)!, required_credits: credit(row.required_credits)!,
        actual_credits: credit(row.actual_credits)!, grade: text(row.grade, true), reported_pass: pass, note: text(row.note, true) };
    }
    if (kind === "module") {
      const row = object(value, ["kind", "title", "required_credits", "actual_credits", "reported_status", "note"]);
      return { kind: "module" as const, title: text(row.title)!, required_credits: credit(row.required_credits)!,
        actual_credits: credit(row.actual_credits)!, reported_status: text(row.reported_status, true), note: text(row.note, true) };
    }
    return fail("完成情况行类型无效。");
  });
  if (rows.filter(r => r.kind === "course").length > DEGREE_LIMITS.courses || rows.filter(r => r.kind === "module").length > DEGREE_LIMITS.modules)
    fail("完成情况课程或分类条数超限。");
  return { schema_version: "1.0.0", kind: "degree_completion_snapshot", program: text(plan.program, true), cohort: text(plan.cohort, true),
    source: source as unknown as DegreePlanImport["source"], rows, summary: {
      required_credits: credit(summary.required_credits, true), completed_credits: credit(summary.completed_credits, true), actual_credits: credit(summary.actual_credits, true),
      reported_result: text(summary.reported_result, true), reviewed_at: text(summary.reviewed_at, true), note: text(summary.note, true) } };
}
/** Expand cell spans only; no values from the surrounding account header are read. */
function tableGrid(table: HTMLTableElement): HTMLTableCellElement[][] {
  const rows = [...table.querySelectorAll("tr")].filter(r => r.closest("table") === table);
  if (rows.length > 2500) fail("完成表过大，请分段核对。");
  const grid: HTMLTableCellElement[][] = [];
  rows.forEach((row, y) => {
    grid[y] ??= []; let x = 0;
    for (const cell of row.cells) {
      while (grid[y][x]) x++;
      const rs = cell.rowSpan === 0 ? rows.length - y : cell.rowSpan, cs = cell.colSpan;
      if (rs > rows.length - y || cs > 32 || x + cs > 32 || cell.querySelector("table")) fail("完成表合并结构异常，未导出不完整报告。");
      for (let dy = 0; dy < rs; dy++) for (let dx = 0; dx < cs; dx++) {
        grid[y + dy] ??= [];
        if (grid[y + dy][x + dx]) fail("完成表合并单元格重叠。");
        grid[y + dy][x + dx] = cell;
      }
      x += cs;
    }
  });
  return grid;
}
export function extractDegreePlanFromDoc(doc: Document, pageUrl?: string): DegreePlanImport {
  if (pageUrl && new URL(pageUrl).origin + new URL(pageUrl).pathname !== DEGREE_PLAN_URL) fail("只支持教务「计划完成情况」页面。");
  if (doc.querySelector('input[type="password"]')) fail("检测到登录页，拒绝读取；请本人登录后打开计划完成情况。");
  const tables = [...doc.querySelectorAll("table")];
  const matches = tables.filter(t => [...t.rows].some(r => r.closest("table") === t &&
    [...r.cells].some(c => head(c.textContent ?? "") === "是否通过") && [...r.cells].some(c => head(c.textContent ?? "") === "实修学分")));
  if (matches.length !== 1) fail("未找到唯一的完成情况明细表；请等待加载完成，不导出空报告。");
  const grid = tableGrid(matches[0]);
  const headerIndex = grid.findIndex(row => row.some(c => head(c.textContent ?? "") === "是否通过"));
  const headers = grid[headerIndex].map(c => head(c.textContent ?? ""));
  const indexes = Object.fromEntries(Object.entries({ code: ["课程序号", "课程代码", "课程编号"], title: ["课程名称"],
    required: ["要求学分"], actual: ["实修学分"], grade: ["成绩"], pass: ["是否通过"], note: ["备注"] })
    .map(([key, aliases]) => [key, headers.findIndex(h => aliases.includes(h))]));
  if (Object.values(indexes).some(i => i < 0)) fail("完成情况表头不匹配，未猜测字段或导出残缺数据。");
  const rows: DegreePlanImport["rows"] = [];
  for (const cells of grid.slice(headerIndex + 1)) {
    if (!cells.length) continue;
    const get = (key: string) => clean(cells[indexes[key]]?.textContent ?? "");
    if (cells[indexes.code] === cells[indexes.title] && cells[indexes.title]?.colSpan > 1) {
      rows.push({ kind: "module", title: get("title"), required_credits: get("required"), actual_credits: get("actual"), reported_status: get("pass") || null, note: get("note") || null });
    } else {
      rows.push({ kind: "course", course_code: get("code"), title: get("title"), required_credits: get("required"),
        actual_credits: get("actual"), grade: get("grade") || null, reported_pass: get("pass") || null, note: get("note") || null });
    }
  }
  // Whitelist exact summary labels and read ONLY the immediately following value.
  const metadata: Record<string, string> = {};
  const allowed = ["专业/专业方向:", "年级:", "要求学分/完成学分/实修学分:", "审核结果:", "审核时间:", "备注:"];
  const summaryTables = tables.filter(t => [...t.rows].some(r => r.closest("table") === t && [...r.cells].some(c => head(c.textContent ?? "") === allowed[2])));
  if (summaryTables.length > 1) fail("报告总览不唯一，请核对来源。");
  if (summaryTables.length) for (const row of summaryTables[0].rows) for (const cell of row.cells) {
    const label = head(cell.textContent ?? "");
    if (allowed.includes(label)) metadata[label] = clean(cell.nextElementSibling?.textContent ?? "");
  }
  const totals = metadata[allowed[2]]?.split("/").map(clean) ?? [];
  if (totals.length && totals.length !== 3) fail("总览学分格式未识别。");
  return validateDegreePlanImport({ schema_version: "1.0.0", kind: "degree_completion_snapshot", program: metadata[allowed[0]] || null,
    cohort: metadata[allowed[1]] || null, source: { kind: pageUrl ? "visible_dom" : "file", origin: pageUrl ? new URL(pageUrl).origin : null, pathname: pageUrl ? new URL(pageUrl).pathname : null },
    summary: { required_credits: totals[0] ?? null, completed_credits: totals[1] ?? null, actual_credits: totals[2] ?? null,
      reported_result: metadata[allowed[3]] || null, reviewed_at: metadata[allowed[4]] || null, note: metadata[allowed[5]] || null }, rows });
}
export function parseDegreePlanFile(name: string, content: string): DegreePlanImport {
  if (new TextEncoder().encode(content).length > DEGREE_LIMITS.bytes) fail("计划完成情况文件超过 1 MB。");
  if (/\.json$/i.test(name)) return validateDegreePlanImport(JSON.parse(content.replace(/^\uFEFF/, "")));
  if (/\.html?$/i.test(name)) return extractDegreePlanFromDoc(new DOMParser().parseFromString(content, "text/html"));
  fail("请上传计划完成情况 JSON 或教务保存 HTML；PDF/截图不能直接当作已解析报告。");
}
export function degreePlanWarnings(plan: DegreePlanImport): string[] {
  const warnings = ["这是教务计划完成情况快照，不作为最终审核或毕业资格结论。",
    "保留学校原始完成/实修学分，不相加父子分类、不按成绩重新计分；预审可能含在读课程。",
    "只包含本次已加载表格，换学期或成绩更新后须重新导出。"];
  if (plan.rows.some(r => r.kind === "course" && /在读/.test(r.note ?? ""))) warnings.push("存在在读课程；即使教务显示‘是’，也不能据此认定已取得学分。");
  if (!plan.summary.reported_result) warnings.push("报告总览未识别，请核对教务原页。课程明细不替代总览结论。");
  const codes = plan.rows.filter((r): r is DegreePlanCourse => r.kind === "course").map(r => r.course_code);
  if (new Set(codes).size !== codes.length) warnings.push("课程代码重复：保留原始分类顺序，不去重或重复计学分。");
  return warnings;
}
