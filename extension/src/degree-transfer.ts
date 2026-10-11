/**
 * 「培养计划」独立消息链路（degree-transfer，service worker 侧）。
 *
 * 只识别两个消息：
 * - degree-observation：教务培养计划页 content script（degree-content）回传的观察值；
 * - degree-bridge-ready：工具站 /tools/degree 桥接脚本（degree-app-bridge）拉取暂存观察值。
 *
 * 课表链路的消息（schedule-observation / schedule-auto-observation / app-bridge-ready /
 * submit-confirmed-draft）一律 handled:false，交回 background 既有分支处理。
 * 本模块只读写 degree-transfer:<uuid> 命名空间的 session 键，
 * 绝不读取、消费或删除课表的 transfer:* 键。
 *
 * Codex 集成方式（background 的 chrome.runtime.onMessage 内）：
 *
 *   const route = handleDegreeMessage(raw, sender, chrome);
 *   if (route.handled) {
 *     void route.response.then(sendResponse);
 *     return true; // 异步响应
 *   }
 *   // 否则继续既有的 parseMessage/课表分支
 */
import { isDegreePage } from "../../packages/import-core/src/degree-page";
import type { DegreeTableObservation } from "../../packages/import-core/src/degree-page";

import { APP_ORIGINS } from "./config";

export const DEGREE_OBSERVATION_MESSAGE = "degree-observation";
export const DEGREE_BRIDGE_READY_MESSAGE = "degree-bridge-ready";

/** session 键命名空间：与课表的 transfer:<uuid> 完全隔离。 */
export const DEGREE_TRANSFER_KEY_PREFIX = "degree-transfer:";
/** 十分钟一次性票据。 */
export const DEGREE_TRANSFER_TTL_MS = 10 * 60 * 1000;

export const DEGREE_TOOL_PATH = "/tools/degree";
export const DEGREE_TOOL_TRANSFER_PARAM = "degree_transfer_id";

/** 固定来源地址：不接受任何带查询串/片段的变体。 */
export const DEGREE_SOURCE_URL = "https://eamis.nankai.edu.cn/eams/myPlanCompl.action";

/** 已知表头：与 import-core degree-page / degree-content 保持一致，集成时需同步。 */
export const DEGREE_TABLE_HEADERS = [
  "课程序号",
  "课程名称",
  "要求学分",
  "实修学分",
  "成绩",
  "是否通过",
  "备注",
];

export const MAX_DEGREE_PAYLOAD_BYTES = 1_048_576;
export const MAX_DEGREE_ROWS = 2000;
export const MAX_DEGREE_CELLS_PER_ROW = 64;
export const MAX_DEGREE_CELL_LENGTH = 4096;
export const MAX_DEGREE_HEADERS = 64;

const TRANSFER_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** 身份信息一律不得进入培养计划观察值：命中即整包拒绝，不做脱敏后转发。 */
const IDENTITY_PATTERN =
  /学号\s*[:：]|姓名\s*[:：]|身份证|考生号|学籍号|验证码|密码|手机号|一卡通|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\b1[3-9]\d{9}\b/;

export type DegreeTransferResponse =
  | { ok: true; transferId?: string; expiresAt?: number; observation?: unknown }
  | { ok: false; error: string };

/** background 路由结果：handled=false 表示不是培养计划消息，应继续既有分支。 */
export type DegreeMessageRoute =
  | { handled: false }
  | { handled: true; response: Promise<DegreeTransferResponse> };

export interface DegreeMessageSender {
  id?: string;
  url?: string;
  tab?: { url?: string };
}

export interface DegreeTransferChromeApi {
  runtime: { id: string };
  storage: {
    session: {
      get(key: string): Promise<Record<string, unknown>>;
      set(items: Record<string, unknown>): Promise<void>;
      remove(key: string): Promise<void>;
    };
  };
  tabs: { create(createProperties: { url: string }): Promise<unknown> | unknown };
}

export interface DegreeTransferOptions {
  now?: () => number;
  randomUUID?: () => string;
}

export class DegreeTransferError extends Error {
  readonly code: string;

  constructor(code: string, reason: string) {
    super(`${code}: ${reason}`);
    this.name = "DegreeTransferError";
    this.code = code;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readMessageType(raw: unknown): string | null {
  if (!isRecord(raw)) return null;
  return typeof raw.type === "string" ? raw.type : null;
}

export function degreeTransferKey(transferId: string): string {
  return `${DEGREE_TRANSFER_KEY_PREFIX}${transferId}`;
}

export function isDegreeTransferId(value: unknown): value is string {
  return typeof value === "string" && TRANSFER_ID_PATTERN.test(value);
}

/** 工具站只允许固定 origin（config.APP_ORIGINS）+ 精确 /tools/degree。 */
export function isDegreeToolUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return APP_ORIGINS.includes(parsed.origin) && parsed.pathname === DEGREE_TOOL_PATH;
  } catch {
    return false;
  }
}

/** 目标地址由常量拼装，不接受调用方/页面提供的任意 URL。 */
export function buildDegreeToolUrl(transferId: string): string {
  if (!isDegreeTransferId(transferId)) {
    throw new DegreeTransferError("INVALID_DEGREE_TRANSFER_ID", "转交 id 必须是 uuid");
  }
  const url = new URL(DEGREE_TOOL_PATH, APP_ORIGINS[0]);
  url.searchParams.set(DEGREE_TOOL_TRANSFER_PARAM, transferId);
  return url.toString();
}

export function degreePayloadBytes(payload: unknown): number {
  let text: string | undefined;
  try {
    text = JSON.stringify(payload);
  } catch {
    return Number.POSITIVE_INFINITY;
  }
  if (typeof text !== "string") return 0;
  return typeof TextEncoder === "undefined" ? text.length : new TextEncoder().encode(text).length;
}

/**
 * 严格校验 content script 回传的观察值：
 * kind / 固定 sourceURL / 未核查状态 / 表头 / 行与单元格 / 大小 / 身份字段。
 */
export function validateDegreeObservation(payload: unknown): DegreeTableObservation {
  const bytes = degreePayloadBytes(payload);
  if (!Number.isFinite(bytes)) {
    throw new DegreeTransferError("MALFORMED_DEGREE_PAYLOAD", "payload 无法序列化");
  }
  if (bytes > MAX_DEGREE_PAYLOAD_BYTES) {
    throw new DegreeTransferError("DEGREE_PAYLOAD_TOO_LARGE", `payload 超过 ${MAX_DEGREE_PAYLOAD_BYTES} 字节`);
  }
  if (!isRecord(payload)) {
    throw new DegreeTransferError("MALFORMED_DEGREE_PAYLOAD", "payload 不是对象");
  }
  if (payload.kind !== "degree-table-observation") {
    throw new DegreeTransferError("UNEXPECTED_DEGREE_KIND", "kind 不是 degree-table-observation");
  }

  const source = payload.source;
  if (!isRecord(source)) {
    throw new DegreeTransferError("MALFORMED_DEGREE_SOURCE", "缺少 source");
  }
  if (source.url !== DEGREE_SOURCE_URL) {
    throw new DegreeTransferError("UNEXPECTED_DEGREE_SOURCE_URL", "source.url 必须是固定的培养计划页地址");
  }
  if (typeof source.captured_at !== "string" || !Number.isFinite(Date.parse(source.captured_at))) {
    throw new DegreeTransferError("INVALID_CAPTURE_TIME", "captured_at 不是有效时间");
  }
  if (source.coverage !== "unknown" || source.adapter_verified !== false) {
    throw new DegreeTransferError(
      "DEGREE_ADAPTER_STATE_INVALID",
      "适配器未核查状态必须保持 coverage=unknown / adapter_verified=false",
    );
  }

  const headers = payload.headers;
  if (
    !Array.isArray(headers) ||
    headers.length === 0 ||
    headers.length > MAX_DEGREE_HEADERS ||
    headers.some((header) => typeof header !== "string")
  ) {
    throw new DegreeTransferError("MALFORMED_DEGREE_HEADERS", "headers 必须是非空字符串数组");
  }
  const headerTexts = headers as string[];
  if (!DEGREE_TABLE_HEADERS.every((header) => headerTexts.includes(header))) {
    throw new DegreeTransferError("UNSUPPORTED_DEGREE_HEADERS", "headers 缺少已知表头");
  }

  const rows = payload.rows;
  if (!Array.isArray(rows) || rows.length === 0) {
    throw new DegreeTransferError("EMPTY_DEGREE_ROWS", "rows 不能为空");
  }
  if (rows.length > MAX_DEGREE_ROWS) {
    throw new DegreeTransferError("DEGREE_TABLE_TOO_LARGE", `行数超过 ${MAX_DEGREE_ROWS}`);
  }
  rows.forEach((row, index) => {
    if (!isRecord(row)) {
      throw new DegreeTransferError("MALFORMED_DEGREE_ROW", `第 ${index + 1} 行不是对象`);
    }
    if (typeof row.locator !== "string" || row.locator.length === 0 || row.locator.length > 128) {
      throw new DegreeTransferError("MALFORMED_DEGREE_ROW", `第 ${index + 1} 行 locator 无效`);
    }
    const cells = row.cells;
    if (!Array.isArray(cells) || cells.length === 0 || cells.length > MAX_DEGREE_CELLS_PER_ROW) {
      throw new DegreeTransferError("MALFORMED_DEGREE_CELLS", `第 ${index + 1} 行 cells 无效`);
    }
    for (const cell of cells) {
      if (typeof cell !== "string") {
        throw new DegreeTransferError("MALFORMED_DEGREE_CELL", `第 ${index + 1} 行存在非字符串单元格`);
      }
      if (cell.length > MAX_DEGREE_CELL_LENGTH) {
        throw new DegreeTransferError("DEGREE_CELL_TOO_LARGE", `第 ${index + 1} 行单元格过大`);
      }
    }
  });

  if (IDENTITY_PATTERN.test(JSON.stringify(payload))) {
    throw new DegreeTransferError("IDENTITY_IN_DEGREE_PAYLOAD", "payload 中出现身份信息字段");
  }

  return payload as unknown as DegreeTableObservation;
}

async function routeDegreeObservation(
  raw: Record<string, unknown>,
  sender: DegreeMessageSender,
  chromeApi: DegreeTransferChromeApi,
  options: Required<DegreeTransferOptions>,
): Promise<DegreeTransferResponse> {
  const pageUrl = typeof sender.url === "string" ? sender.url : "";
  if (!isDegreePage(pageUrl)) return { ok: false, error: "SENDER_REJECTED" };
  if (typeof sender.tab?.url === "string" && !isDegreePage(sender.tab.url)) {
    return { ok: false, error: "SENDER_REJECTED" };
  }

  let observation: DegreeTableObservation;
  try {
    observation = validateDegreeObservation(raw.payload);
  } catch (error) {
    return {
      ok: false,
      error: error instanceof DegreeTransferError ? error.code : "MALFORMED_DEGREE_PAYLOAD",
    };
  }

  const transferId = options.randomUUID();
  if (!isDegreeTransferId(transferId)) return { ok: false, error: "TRANSFER_ID_UNAVAILABLE" };

  const expiresAt = options.now() + DEGREE_TRANSFER_TTL_MS;
  await chromeApi.storage.session.set({
    [degreeTransferKey(transferId)]: { observation, expiresAt },
  });
  await chromeApi.tabs.create({ url: buildDegreeToolUrl(transferId) });
  return { ok: true, transferId, expiresAt };
}

const consumingTransfers = new WeakMap<DegreeTransferChromeApi, Set<string>>();

async function routeDegreeBridgeReady(
  sender: DegreeMessageSender,
  chromeApi: DegreeTransferChromeApi,
  options: Required<DegreeTransferOptions>,
): Promise<DegreeTransferResponse> {
  const pageUrl =
    typeof sender.url === "string"
      ? sender.url
      : typeof sender.tab?.url === "string"
        ? sender.tab.url
        : "";
  if (!isDegreeToolUrl(pageUrl)) return { ok: false, error: "SENDER_REJECTED" };

  let transferId: string | null = null;
  try {
    transferId = new URL(pageUrl).searchParams.get(DEGREE_TOOL_TRANSFER_PARAM);
  } catch {
    return { ok: false, error: "SENDER_REJECTED" };
  }
  if (!isDegreeTransferId(transferId)) return { ok: false, error: "MISSING_DEGREE_TRANSFER_ID" };

  const key = degreeTransferKey(transferId);
  const consuming = consumingTransfers.get(chromeApi) ?? new Set<string>();
  consumingTransfers.set(chromeApi, consuming);
  if (consuming.has(key)) return { ok: false, error: "DEGREE_TRANSFER_BUSY" };
  consuming.add(key);
  try {
    const stored = await chromeApi.storage.session.get(key);
    const item = stored[key];
    if (!isRecord(item)) return { ok: false, error: "NO_DEGREE_TRANSFER" };

  // 一次性票据：无论是否过期都先消费本命名空间的键（只删 degree-transfer:）。
    await chromeApi.storage.session.remove(key);
    if (typeof item.expiresAt !== "number" || !Number.isFinite(item.expiresAt) || item.expiresAt <= options.now()
      || item.expiresAt > options.now() + DEGREE_TRANSFER_TTL_MS) {
      return { ok: false, error: "DEGREE_TRANSFER_EXPIRED" };
    }
    if (item.observation === undefined || item.observation === null) {
      return { ok: false, error: "NO_DEGREE_TRANSFER" };
    }
    return { ok: true, observation: validateDegreeObservation(item.observation) };
  } finally {
    consuming.delete(key);
  }
}

async function routeDegreeMessage(
  type: string,
  raw: unknown,
  sender: DegreeMessageSender,
  chromeApi: DegreeTransferChromeApi,
  options: Required<DegreeTransferOptions>,
): Promise<DegreeTransferResponse> {
  // 只接受本扩展自己的 content script（扩展 id 必须一致）。
  if (sender.id !== chromeApi.runtime.id) return { ok: false, error: "SENDER_REJECTED" };
  if (!isRecord(raw)) return { ok: false, error: "MALFORMED_DEGREE_MESSAGE" };
  if (type === DEGREE_OBSERVATION_MESSAGE) {
    return routeDegreeObservation(raw, sender, chromeApi, options);
  }
  return routeDegreeBridgeReady(sender, chromeApi, options);
}

/**
 * background 路由入口。
 * - handled:false → 不是培养计划消息（含所有课表链路消息），background 继续既有分支；
 * - handled:true  → 由本模块处理，response 永不会 reject，交给 sendResponse 即可。
 */
export function handleDegreeMessage(
  raw: unknown,
  sender: DegreeMessageSender,
  chromeApi: DegreeTransferChromeApi,
  options: DegreeTransferOptions = {},
): DegreeMessageRoute {
  const type = readMessageType(raw);
  if (type !== DEGREE_OBSERVATION_MESSAGE && type !== DEGREE_BRIDGE_READY_MESSAGE) {
    return { handled: false };
  }
  const resolved: Required<DegreeTransferOptions> = {
    now: options.now ?? (() => Date.now()),
    randomUUID: options.randomUUID ?? (() => globalThis.crypto.randomUUID()),
  };
  const response = routeDegreeMessage(type, raw, sender, chromeApi, resolved).catch(
    (): DegreeTransferResponse => ({ ok: false, error: "DEGREE_INTERNAL_ERROR" }),
  );
  return { handled: true, response };
}
