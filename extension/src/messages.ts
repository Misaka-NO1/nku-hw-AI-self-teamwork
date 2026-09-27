/**
 * 扩展内部消息协议（B06）。
 *
 * content script 发来的消息一律视为不可信：service worker 必须校验
 * sender.id、sender.tab.url、origin、消息类型、字段结构与大小。
 * 提交草稿只接受扩展自己的独立预览页发起的 submit-confirmed-draft，
 * 不接受教务 content script 的 confirmed:true。
 */

export const MESSAGE_TYPES = [
  "extract-visible-schedule",
  "schedule-observation",
  "open-import-preview",
  "submit-confirmed-draft",
] as const;

export type MessageType = (typeof MESSAGE_TYPES)[number];

export interface ExtensionMessage {
  type: MessageType;
  payload: unknown;
}

export const MESSAGE_LIMITS = {
  maxPayloadBytes: 1024 * 1024,
  maxRows: 2000,
};

export function parseMessage(raw: unknown): ExtensionMessage | null {
  if (typeof raw !== "object" || raw === null) {
    return null;
  }
  const candidate = raw as { type?: unknown; payload?: unknown };
  if (typeof candidate.type !== "string" || !MESSAGE_TYPES.includes(candidate.type as MessageType)) {
    return null;
  }
  const size = new TextEncoder().encode(JSON.stringify(candidate.payload ?? null)).length;
  if (size > MESSAGE_LIMITS.maxPayloadBytes) {
    return null;
  }
  return { type: candidate.type as MessageType, payload: candidate.payload ?? null };
}

export interface SenderInfo {
  id?: string;
  url?: string;
  tabUrl?: string;
}

/**
 * 校验消息发送者：
 * - content script 只允许发送 schedule-observation（且其页面 URL 已过白名单）；
 * - submit-confirmed-draft 只允许来自扩展自身的预览页（chrome-extension://<id>/...）；
 * - 其他扩展或网页一律拒绝。
 */
export function isSenderAllowed(
  message: ExtensionMessage,
  sender: SenderInfo,
  extensionId: string,
  isUrlWhitelisted: (url: string) => boolean,
): boolean {
  if (sender.id !== undefined && sender.id !== extensionId) {
    return false;
  }
  if (message.type === "submit-confirmed-draft") {
    const url = sender.url ?? "";
    return url.startsWith(`chrome-extension://${extensionId}/`);
  }
  if (message.type === "schedule-observation") {
    const pageUrl = sender.tabUrl ?? sender.url ?? "";
    return isUrlWhitelisted(pageUrl);
  }
  return sender.id === extensionId || sender.id === undefined;
}
