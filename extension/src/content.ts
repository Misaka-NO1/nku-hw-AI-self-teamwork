import { REQUIRED_TABLE_HEADERS } from "@campus/import-core";
import type { PageObservation } from "@campus/import-core";

/**
 * content script 的白名单课程区域提取。
 *
 * 只读取课程表格的文本内容：不读 document.cookie、密码框、SSO 字段、
 * localStorage 认证项，不抓取整页 outerHTML，不请求任何网络资源。
 * 页面结构不符合预期时抛出带 file-fallback 提示的错误（EXT-03）。
 */

export class UnsupportedPageError extends Error {
  readonly code = "UNSUPPORTED_PAGE";
  readonly fallback = "请改用文件导入（JSON/CSV/HTML 导出）";

  constructor(reason: string) {
    super(`UNSUPPORTED_PAGE: ${reason}`);
  }
}

export function extractCourseObservation(
  doc: Document,
  options: { pageUrl: string; selectedTerm?: string | null; selectedWeeks?: number[] },
): PageObservation {
  const pageUrl = new URL(options.pageUrl);
  if (doc.querySelector("input[type=password]") && !doc.querySelector("table")) {
    throw new UnsupportedPageError("检测到登录页，拒绝读取");
  }

  let headers: string[] | null = null;
  let rows: string[][] = [];
  for (const table of [...doc.querySelectorAll("table")]) {
    const headerRow = table.querySelector("thead tr") ?? table.querySelector("tr");
    const candidateHeaders = [...(headerRow?.querySelectorAll("th,td") ?? [])].map((cell) =>
      (cell.textContent ?? "").trim(),
    );
    if (!REQUIRED_TABLE_HEADERS.every((header) => candidateHeaders.includes(header))) {
      continue;
    }
    headers = candidateHeaders;
    rows = [...table.querySelectorAll("tr")]
      .filter((row) => {
        const cells = [...row.querySelectorAll("th,td")];
        return cells.length > 0 && cells.some((cell) => cell.tagName.toLowerCase() !== "th");
      })
      .map((row) =>
        [...row.querySelectorAll("th,td")].map((cell) => (cell.textContent ?? "").trim()),
      );
    break;
  }

  if (headers === null) {
    throw new UnsupportedPageError("课程表结构不符合预期（页面可能已改版），不导入空课表");
  }

  return {
    origin: pageUrl.origin,
    pathname: pageUrl.pathname,
    frameOrigin: null,
    tableHeaders: headers,
    rows,
    selectedTerm: options.selectedTerm ?? null,
    selectedWeeks: options.selectedWeeks ?? [],
    hasPagination: doc.querySelector("[data-pagination], .pagination") !== null,
    hasVirtualRows: doc.querySelector("[data-virtual], .virtual-list") !== null,
  };
}
