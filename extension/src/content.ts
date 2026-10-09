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
    selectedTerm: options.selectedTerm ?? (doc.querySelector<HTMLInputElement>('input[id$="Semester"]')?.value || null),
    selectedWeeks: options.selectedWeeks ?? (()=>{const selector=doc.querySelector<HTMLSelectElement>('#startWeek');const match=selector?.selectedOptions[0]?.textContent?.match(/第(\d+)周/);return match ? [Number(match[1])] : [];})(),
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

/**
 * 页内「读取并导入」按钮（EXT-B12）：content script 在教务课表页自动注入后，
 * 等课表网格出现，在页面右下角注入一个 Shadow DOM 悬浮按钮。
 * 只在用户点击时读取课程表格文本（不读密码 / Cookie / SSO 字段），
 * 提取成功后回传 schedule-auto-observation，由 service worker 打开核对页。
 * 登录页（有密码框且无表格）不注入按钮，用户登录跳转后页面重载会重新注入。
 */
const BUTTON_RETRY_MS = 1000;
const BUTTON_MAX_ATTEMPTS = 30;

const BUTTON_STYLES = `
  :host { all: initial; }
  #wrap { position: fixed; right: 24px; bottom: 24px; z-index: 2147483647;
    font-family: system-ui, "PingFang SC", "Microsoft YaHei", sans-serif; }
  button { display: block; padding: 12px 20px; border: none; border-radius: 999px;
    background: #1d4ed8; color: #fff; font-size: 15px; font-weight: 600;
    cursor: pointer; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
  button:hover { background: #1e40af; }
  button:disabled { background: #94a3b8; cursor: default; }
  #tip { margin-top: 8px; padding: 6px 10px; border-radius: 8px; background: rgba(15,23,42,.85);
    color: #fff; font-size: 12px; max-width: 260px; display: none; }
`;

export function mountImportButton(
  chromeApi: typeof chrome,
  doc: Document,
  pageUrl: string,
  options: { maxAttempts?: number; retryMs?: number } = {},
): void {
  const maxAttempts = options.maxAttempts ?? BUTTON_MAX_ATTEMPTS;
  const retryMs = options.retryMs ?? BUTTON_RETRY_MS;
  let attempts = 0;
  const tryMount = () => {
    attempts += 1;
    // 登录页：不注入，等用户登录后页面跳转/重载重新注入
    if (doc.querySelector("input[type=password]") && !doc.querySelector("table")) return;
    if (!doc.querySelector(EAMIS_GRID_SELECTOR)) {
      if (attempts < maxAttempts) setTimeout(tryMount, retryMs);
      return;
    }
    if (doc.getElementById("campus-schedule-import-host")) return;

    const host = doc.createElement("div");
    host.id = "campus-schedule-import-host";
    const shadow = host.attachShadow({ mode: "closed" });
    const style = doc.createElement("style");
    style.textContent = BUTTON_STYLES;
    const wrap = doc.createElement("div");
    wrap.id = "wrap";
    const button = doc.createElement("button");
    button.type = "button";
    button.textContent = "📥 读取并导入课表";
    const tip = doc.createElement("div");
    tip.id = "tip";
    wrap.append(button, tip);
    shadow.append(style, wrap);
    doc.body.appendChild(host);

    const showTip = (text: string, ms = 6000) => {
      tip.textContent = text;
      tip.style.display = "block";
      setTimeout(() => { tip.style.display = "none"; }, ms);
    };

    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "读取中…";
      try {
        // 只读取课程表格文本：不碰 cookie、密码框、SSO 字段、整页 HTML
        const observation = extractCourseObservation(doc, { pageUrl });
        const response = await chromeApi.runtime.sendMessage({ type: "schedule-auto-observation", payload: observation });
        if (!response?.ok) throw new Error("无法打开核对页，请刷新后重试");
        button.textContent = "✓ 已读取，已打开核对页";
        showTip("已读取课表（不含任何登录信息），即将打开核对页面。");
        setTimeout(() => {
          button.disabled = false;
          button.textContent = "📥 读取并导入课表";
        }, 4000);
      } catch (error) {
        button.disabled = false;
        button.textContent = "📥 读取并导入课表";
        const reason = error instanceof Error ? error.message : String(error);
        showTip(`读取失败：${reason}。可改用核对页里的文件导入。`, 9000);
      }
    });
  };
  tryMount();
}

// 仅在教务域名由 manifest 自动注入时挂载按钮；window 标记避免重复注入重复挂载
declare global {
  interface Window {
    __campusImportButtonMounted?: boolean;
  }
}
if (
  typeof chrome !== "undefined" &&
  chrome.runtime?.id &&
  typeof window !== "undefined" &&
  !window.__campusImportButtonMounted &&
  location.hostname === "eamis.nankai.edu.cn"
) {
  window.__campusImportButtonMounted = true;
  mountImportButton(chrome, document, location.href);
}
