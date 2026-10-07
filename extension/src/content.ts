import { extractEamisGridFromDoc, REQUIRED_TABLE_HEADERS } from "@campus/import-core";
import type { PageObservation } from "@campus/import-core";

import { parseMessage } from "./messages";

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

/**
 * eamis「我的课表」网格提取（B08，nku-adapter-v1）：行=节次、列=星期，
 * rowSpan 展开为「课程条目/星期/节次(p-q)」三列观察值，
 * 条目文本保持原文，由 import-core 的 eamis 解析器切分。
 * 提取实现与 HTML 文件导入共用（import-core extractEamisGridFromDoc）。
 */
const EAMIS_GRID_SELECTOR = "#manualArrangeCourseTable";

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

  // 优先匹配 eamis「我的课表」网格（nku-adapter-v1，行=节次 × 列=星期）
  if (doc.querySelector(EAMIS_GRID_SELECTOR)) {
    const grid = extractEamisGridFromDoc(doc);
    if (grid === null) {
      throw new UnsupportedPageError("eamis 课表网格结构不符合预期（页面可能已改版），不导入空课表");
    }
    headers = grid.headers;
    rows = grid.rows;
  }

  if (headers === null) {
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

/**
 * content script 运行入口：接收 service worker 的 extract-visible-schedule，
 * 提取白名单课程区域后回传 schedule-observation；失败时回传结构化错误。
 */
export function registerContentListener(
  chromeApi: typeof chrome,
  doc: Document,
  pageUrl: string,
): void {
  chromeApi.runtime.onMessage.addListener((raw, _sender, sendResponse) => {
    const message = parseMessage(raw);
    if (!message || message.type !== "extract-visible-schedule") {
      return false;
    }
    try {
      const observation = extractCourseObservation(doc, { pageUrl });
      void chromeApi.runtime.sendMessage({
        type: "schedule-observation",
        payload: observation,
      });
      sendResponse({ ok: true });
    } catch (error) {
      const unsupported = error as Partial<UnsupportedPageError>;
      sendResponse({
        ok: false,
        error: {
          code: unsupported.code ?? "UNKNOWN",
          message: error instanceof Error ? error.message : String(error),
          fallback: unsupported.fallback ?? null,
        },
      });
    }
    return false;
  });
}

// 真实 content script 环境中自动注册；单测中显式调用 registerContentListener
if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  registerContentListener(chrome, document, location.href);
}
