/**
 * 「培养计划」独立读取链路（degree-content）。
 *
 * 与课表链路（content.ts）完全独立：
 * - 复用 import-core 的独立 isDegreePage / extractDegreeTable，不共用课表适配器；
 * - 只有用户点击「读取培养计划」按钮时才读取页面文本，挂载阶段不采集；
 * - 只按已知表头在页面里寻找唯一候选表，不猜 id / CSS 选择器、不读取整页 HTML；
 * - 真实教务 DOM 尚未核查：观察值保持 adapter_verified=false、coverage="unknown"，
 *   不伪造「已核查」结论；
 * - 结果只通过独立的 degree-observation 消息交给 service worker（degree-transfer）。
 *
 * import-core 的 barrel（packages/import-core/src/index.ts）尚未导出 degree-page，
 * 因此这里按相对路径直连该独立模块；若集成时 barrel 统一导出，可改为从
 * "@campus/import-core" 导入，行为不变。
 */
import { extractDegreeTable, isDegreePage } from "../../packages/import-core/src/degree-page";
import type { DegreeTableObservation } from "../../packages/import-core/src/degree-page";

/** 已知表头：与 import-core degree-page 的 HEADERS 保持一致，集成时需同步。 */
export const DEGREE_TABLE_HEADERS = [
  "课程序号",
  "课程名称",
  "要求学分",
  "实修学分",
  "成绩",
  "是否通过",
  "备注",
] as const;

/** 独立消息类型：与课表链路的 schedule-observation / schedule-auto-observation 互不干扰。 */
export const DEGREE_OBSERVATION_MESSAGE = "degree-observation";

/** 我们自己的按钮宿主 id（用于去重），不是对页面结构的猜测。 */
export const DEGREE_BUTTON_HOST_ID = "campus-degree-plan-host";
export const DEGREE_BUTTON_LABEL = "📖 读取培养计划";

export type DegreeContentErrorCode =
  | "UNSUPPORTED_DEGREE_PAGE"
  | "DEGREE_LOGIN_PAGE"
  | "DEGREE_TABLE_NOT_FOUND"
  | "MULTIPLE_DEGREE_TABLES"
  | "DEGREE_OBSERVATION_INVALID";

export class DegreeContentError extends Error {
  readonly code: DegreeContentErrorCode;
  readonly fallback = "可在核对页改用文件导入，或稍后刷新培养计划页重试";

  constructor(code: DegreeContentErrorCode, reason: string) {
    super(`${code}: ${reason}`);
    this.name = "DegreeContentError";
    this.code = code;
  }
}

/** 只需 runtime.sendMessage；便于单测注入假实现。真实 chrome 对象可直接传入。 */
export interface DegreeContentChromeApi {
  runtime: {
    id?: string;
    sendMessage(message: { type: string; payload: unknown }): Promise<unknown>;
  };
}

export interface DegreeButtonOptions {
  label?: string;
  /** 采集时间来源，测试可注入固定时钟。 */
  capturedAt?: () => string;
}

export type DegreeReadResult =
  | { ok: true; observation: DegreeTableObservation }
  | { ok: false; code: string; message: string; fallback: string | null };

/** 判断某一行是否是「已知表头行」：只按表头文本，不依赖 id/class/顺序。 */
function isKnownHeaderRow(row: HTMLTableRowElement): boolean {
  const texts = Array.from(row.cells).map((cell) => (cell.textContent ?? "").trim());
  return DEGREE_TABLE_HEADERS.every((header) => texts.includes(header));
}

/**
 * 只寻找唯一候选表：全页扫描 <table>，要求某个行同时包含全部已知表头。
 * 0 个 → 缺表；≥2 个 → 多候选；两种都不猜、不取第一个。
 */
export function findUniqueDegreeTable(doc: Document): HTMLTableElement {
  const candidates: HTMLTableElement[] = [];
  for (const table of Array.from(doc.querySelectorAll("table"))) {
    if (Array.from(table.rows).some(isKnownHeaderRow)) candidates.push(table);
  }
  if (candidates.length === 0) {
    throw new DegreeContentError("DEGREE_TABLE_NOT_FOUND", "页面中没有找到包含已知表头的培养计划表");
  }
  if (candidates.length > 1) {
    throw new DegreeContentError(
      "MULTIPLE_DEGREE_TABLES",
      `页面中出现 ${candidates.length} 个候选表，无法确定唯一培养计划表`,
    );
  }
  return candidates[0];
}

function assertNotLoginPage(doc: Document): void {
  // 登录页一律不读取：密码框是明确的登录信号，不做任何试探性提取。
  if (doc.querySelector("input[type=password]")) {
    throw new DegreeContentError("DEGREE_LOGIN_PAGE", "检测到登录表单，拒绝在登录页读取");
  }
}

/**
 * 提取唯一培养计划表的文本观察值。
 * 复用 import-core 的 extractDegreeTable（含表头/单元格/身份区域/大小校验）。
 */
export function extractDegreeObservation(
  doc: Document,
  pageUrl: string,
  capturedAt: string,
): DegreeTableObservation {
  if (!isDegreePage(pageUrl)) {
    throw new DegreeContentError("UNSUPPORTED_DEGREE_PAGE", "当前页面不是培养计划页（origin+path 不匹配）");
  }
  assertNotLoginPage(doc);
  const table = findUniqueDegreeTable(doc);
  const observation = extractDegreeTable(table, pageUrl, capturedAt);
  // 真实 DOM 未核查：不允许任何环节把它升级成「已核查/完整覆盖」。
  if (observation.source.adapter_verified !== false || observation.source.coverage !== "unknown") {
    throw new DegreeContentError(
      "DEGREE_OBSERVATION_INVALID",
      "观察值不得声称已核查的适配器或完整覆盖",
    );
  }
  return observation;
}

function failureOf(error: unknown): DegreeReadResult {
  if (error instanceof DegreeContentError) {
    return { ok: false, code: error.code, message: error.message, fallback: error.fallback };
  }
  const message = error instanceof Error ? error.message : String(error);
  const code = /^[A-Z][A-Z0-9_]*$/.test(message) ? message : "UNKNOWN_DEGREE_ERROR";
  return { ok: false, code, message, fallback: null };
}

/**
 * 用户点击后的唯一读取入口：提取 → 通过 degree-observation 独立消息回传。
 * 拒绝/失败一律返回结构化结果，不抛异常；失败时绝不发送任何页面内容。
 */
export async function readDegreeObservationOnDemand(
  chromeApi: DegreeContentChromeApi,
  doc: Document,
  pageUrl: string,
  capturedAt: () => string = () => new Date().toISOString(),
): Promise<DegreeReadResult> {
  let observation: DegreeTableObservation;
  try {
    observation = extractDegreeObservation(doc, pageUrl, capturedAt());
  } catch (error) {
    return failureOf(error);
  }
  let response: unknown;
  try {
    response = await chromeApi.runtime.sendMessage({
      type: DEGREE_OBSERVATION_MESSAGE,
      payload: observation,
    });
  } catch (error) {
    return {
      ok: false,
      code: "DEGREE_SEND_FAILED",
      message: "培养计划未成功转交，请重新读取或稍后重试",
      fallback: null,
    };
  }
  if (response === null || typeof response !== "object" || (response as { ok?: unknown }).ok !== true) {
    const error = response && typeof response === "object" ? (response as { error?: unknown }).error : undefined;
    return {
      ok: false,
      code: typeof error === "string" ? error : "DEGREE_TRANSFER_REJECTED",
      message: "培养计划未成功转交，请重新读取或稍后重试",
      fallback: null,
    };
  }
  return { ok: true, observation };
}

/** Shadow DOM 可用时的补充样式（hover/disabled）；基础样式走内联，保证任何环境都可见。 */
const BUTTON_STYLES = `
  button:hover { background: #115e59; }
  button:disabled { background: #94a3b8; cursor: default; }
`;

/** 已挂载的按钮（closed Shadow DOM 下页面脚本拿不到，模块内保留引用便于自检/单测）。 */
const mountedButtons = new WeakMap<Document, HTMLButtonElement>();

/**
 * 自检/单测用：content script 运行在隔离世界，页面脚本无法调用本模块导出，
 * 因此返回自己的按钮元素不会扩大页面能力面。
 */
export function getMountedDegreeButton(doc: Document): HTMLButtonElement | null {
  return mountedButtons.get(doc) ?? null;
}

/**
 * 在培养计划页挂载「读取培养计划」按钮。
 * - 非目标 URL（如课表页、工具站）直接拒绝，返回 false；
 * - 登录页（有密码框）不注入；
 * - 重复调用不会产生第二个按钮；
 * - 挂载阶段不做任何提取，只有点击才走 readDegreeObservationOnDemand。
 */
export function mountDegreeButton(
  chromeApi: DegreeContentChromeApi,
  doc: Document,
  pageUrl: string,
  options: DegreeButtonOptions = {},
): boolean {
  if (!isDegreePage(pageUrl)) return false;
  if (doc.querySelector("input[type=password]")) return false;
  if (doc.getElementById(DEGREE_BUTTON_HOST_ID) || mountedButtons.has(doc)) return false;
  if (!doc.body) return false;

  const label = options.label ?? DEGREE_BUTTON_LABEL;
  const capturedAt = options.capturedAt ?? (() => new Date().toISOString());

  const host = doc.createElement("div");
  host.id = DEGREE_BUTTON_HOST_ID;
  host.style.cssText = "position:fixed;right:24px;bottom:96px;z-index:2147483647;";
  // 优先隔离到 closed Shadow DOM；环境不支持（如无浏览上下文的 Document）时降级为普通容器。
  let root: ParentNode = host;
  try {
    root = host.attachShadow({ mode: "closed" });
    const style = doc.createElement("style");
    style.textContent = BUTTON_STYLES;
    root.append(style);
  } catch {
    root = host;
  }
  const wrap = doc.createElement("div");
  wrap.style.cssText =
    'display:flex;flex-direction:column;align-items:flex-end;font-family:system-ui,"PingFang SC","Microsoft YaHei",sans-serif;';
  const button = doc.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.style.cssText =
    "padding:12px 20px;border:none;border-radius:999px;background:#0f766e;color:#fff;font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25);";
  const tip = doc.createElement("div");
  tip.style.cssText =
    "margin-top:8px;padding:6px 10px;border-radius:8px;background:rgba(15,23,42,.85);color:#fff;font-size:12px;max-width:260px;display:none;";
  wrap.append(button, tip);
  root.append(wrap);
  doc.body.appendChild(host);
  mountedButtons.set(doc, button);

  const showTip = (text: string, ms: number) => {
    tip.textContent = text;
    tip.style.display = "block";
    globalThis.setTimeout(() => {
      tip.style.display = "none";
    }, ms);
  };

  let busy = false;
  button.addEventListener("click", () => {
    if (busy) return;
    busy = true;
    button.disabled = true;
    button.textContent = "读取中…";
    // 只有这一刻才读取页面文本；不碰 cookie、密码框、整页 HTML。
    void readDegreeObservationOnDemand(chromeApi, doc, pageUrl, capturedAt).then((result) => {
      busy = false;
      button.disabled = false;
      if (result.ok) {
        button.textContent = "✓ 已读取培养计划";
        showTip("已读取培养计划（不含学号/姓名等身份信息）。", 6000);
        return;
      }
      button.textContent = label;
      showTip(`读取失败：${result.message}${result.fallback ? `。${result.fallback}` : ""}`, 9000);
    });
  });

  return true;
}

// 真实 content script 环境中自动挂载按钮；单测中显式调用 mountDegreeButton。
// 非培养计划 URL 由 mountDegreeButton 内部拒绝，模块加载本身不做任何提取。
if (
  typeof chrome !== "undefined" &&
  chrome.runtime?.id &&
  typeof document !== "undefined" &&
  typeof location !== "undefined"
) {
  mountDegreeButton(chrome, document, location.href);
}
