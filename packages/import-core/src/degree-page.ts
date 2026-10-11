/** Candidate table observation contract; live DOM adapter is not yet verified.
 * This extracts only a caller-selected curriculum table, never the whole page.
 */
export interface DegreeTableObservation {
  kind: "degree-table-observation";
  source: { url: string; captured_at: string; coverage: "partial" | "unknown"; adapter_verified: false };
  headers: string[];
  rows: { cells: string[]; locator: string }[];
}

const HEADERS = ["课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"];
const LIMIT = 2000;

export function isDegreePage(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.origin === "https://eamis.nankai.edu.cn" && parsed.pathname === "/eams/myPlanCompl.action";
  } catch { return false; }
}

export function extractDegreeTable(table: HTMLTableElement, url: string, capturedAt: string): DegreeTableObservation {
  if (!isDegreePage(url)) throw new Error("UNSUPPORTED_DEGREE_PAGE");
  if (!Number.isFinite(Date.parse(capturedAt))) throw new Error("INVALID_CAPTURE_TIME");
  const sourceRows = Array.from(table.rows);
  if (sourceRows.length > LIMIT) throw new Error("DEGREE_TABLE_TOO_LARGE");
  const headerIndex = sourceRows.findIndex(row => HEADERS.every(header => Array.from(row.cells).some(cell => cell.textContent?.trim() === header)));
  if (headerIndex < 0) throw new Error("UNSUPPORTED_DEGREE_HEADERS");
  const headers = Array.from(sourceRows[headerIndex].cells).map(cell => cell.textContent?.trim() ?? "");
  const rows = sourceRows.slice(headerIndex + 1).map((row, index) => {
    if (row.querySelector("input,textarea,select,script,iframe")) throw new Error("UNSUPPORTED_DEGREE_CELL_CONTENT");
    const cells = Array.from(row.cells).map(cell => cell.textContent?.trim() ?? "");
    if (cells.some(cell => /学号\s*[:：]|姓名\s*[:：]|验证码|密码/.test(cell))) throw new Error("IDENTITY_REGION_IN_DEGREE_TABLE");
    if (cells.some(cell => cell.length > 4096)) throw new Error("DEGREE_CELL_TOO_LARGE");
    return { cells, locator: `table-row:${headerIndex + index + 2}` };
  });
  if (!rows.length) throw new Error("EMPTY_DEGREE_TABLE");
  // Discard query parameters/fragments: they may contain student identifiers.
  return { kind: "degree-table-observation", source: { url: "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", captured_at: capturedAt, coverage: "unknown", adapter_verified: false }, headers, rows };
}
