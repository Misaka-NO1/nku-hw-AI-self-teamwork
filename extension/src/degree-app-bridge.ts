/**
 * 「培养计划」工具站桥接 content script（/tools/degree）。
 *
 * 与课表桥接（app-bridge.ts）完全独立：
 * - 只监听页面自定义事件 campus:degree-import-ready；
 * - 只向 service worker 发送 degree-bridge-ready（由 degree-transfer 处理）；
 * - 只派发 campus:degree-observation，detail 仅为后台校验过的观察值本身；
 * - 不监听/不派发任何课表事件，因此不会消费课表的 transfer:* 票据。
 *
 * 桥接脚本自身不做解析，也不向页面暴露扩展能力。
 */
import { DEGREE_BRIDGE_READY_MESSAGE, DEGREE_TOOL_TRANSFER_PARAM, isDegreeTransferId, isDegreeToolUrl } from "./degree-transfer";

export const DEGREE_IMPORT_READY_EVENT = "campus:degree-import-ready";
export const DEGREE_OBSERVATION_EVENT = "campus:degree-observation";
export const DEGREE_BRIDGE_READY_EVENT = "campus:degree-bridge-ready";
export const DEGREE_READ_ERROR_EVENT = "campus:degree-read-error";

export interface DegreeBridgeChromeApi {
  runtime: {
    id?: string;
    sendMessage(message: { type: string; payload: unknown }): Promise<unknown>;
  };
}

/** 同一个窗口只注册一次，避免重复监听导致重复拉取票据。 */
const registeredWindows = new WeakSet<Window>();

/**
 * 注册培养计划桥接。
 * 非工具站 /tools/degree 页面直接拒绝（含课表导入页），返回 false。
 */
export function registerDegreeAppBridge(
  chromeApi: DegreeBridgeChromeApi,
  win: Window,
  pageUrl: string,
): boolean {
  if (!isDegreeToolUrl(pageUrl)) return false;
  if (!isDegreeTransferId(new URL(pageUrl).searchParams.get(DEGREE_TOOL_TRANSFER_PARAM))) return false;
  if (registeredWindows.has(win)) return false;
  registeredWindows.add(win);

  // React 装好接收监听后才会广播 ready；票据只在此刻拉取一次。
  win.addEventListener(
    DEGREE_IMPORT_READY_EVENT,
    () => {
      void chromeApi.runtime
        .sendMessage({ type: DEGREE_BRIDGE_READY_MESSAGE, payload: null })
        .then((response: unknown) => {
          const result = response as { ok?: boolean; observation?: unknown } | undefined;
          if (!result?.ok || result.observation === undefined || result.observation === null) {
            win.dispatchEvent(new Event(DEGREE_READ_ERROR_EVENT));
            return;
          }
          // 只派发观察值本身，不透传响应中的其它字段（例如转交 id）。
          win.dispatchEvent(
            new CustomEvent(DEGREE_OBSERVATION_EVENT, { detail: result.observation }),
          );
        })
        .catch(() => {
          win.dispatchEvent(new Event(DEGREE_READ_ERROR_EVENT));
        });
    },
    { once: true },
  );

  // 对称于课表桥接：告知页面桥接脚本已就绪（React 可能先于/后于 document_idle 加载）。
  win.dispatchEvent(new Event(DEGREE_BRIDGE_READY_EVENT));
  return true;
}

// 真实 content script 环境中自动注册；单测中显式调用 registerDegreeAppBridge。
// 非目标 URL 由 registerDegreeAppBridge 内部拒绝，模块加载本身不发消息。
if (typeof chrome !== "undefined" && chrome.runtime?.id && typeof window !== "undefined") {
  registerDegreeAppBridge(chrome, window, location.href);
}
