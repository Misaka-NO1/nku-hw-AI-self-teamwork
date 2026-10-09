import { isExtractionAllowed, PRODUCTION_WHITELIST, DEV_FIXTURE_WHITELIST, BACKEND_ORIGIN, APP_ORIGINS, APP_IMPORT_PATH, isAppUrl } from "./config";
import { isSenderAllowed, parseMessage } from "./messages";
import { submitConfirmedDraft, type ImportTicket } from "./tickets";

/**
 * MV3 service worker。
 *
 * - 用户点击扩展图标才尝试注入；注入前做白名单检查（activeTab 不会自动限制域名）。
 * - content script 消息不可信：校验 sender、类型、大小后才处理。
 * - 票据只存 chrome.storage.session；上传由本 worker 发起，不下发给 content script。
 */

const whitelist =
  PRODUCTION_WHITELIST.origins.length > 0 ? PRODUCTION_WHITELIST : DEV_FIXTURE_WHITELIST;

declare const chrome: typeof globalThis.chrome;

function isAllowedUrl(url: string): boolean {
  return isExtractionAllowed(url, whitelist);
}

chrome.action.onClicked.addListener(async (tab) => {
  if (tab.id === undefined || !tab.url || !isAllowedUrl(tab.url)) {
    // EXT-01：非白名单域名不注入、不解析、不上传
    return;
  }
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["dist/content.js"],
  });
  chrome.tabs.sendMessage(tab.id, { type: "extract-visible-schedule", payload: null });
});

chrome.runtime.onMessage.addListener((raw, sender, sendResponse) => {
  const message = parseMessage(raw);
  if (!message) {
    return false;
  }
  const allowed = isSenderAllowed(
    message,
    { id: sender.id, url: sender.url, tabUrl: sender.tab?.url },
    chrome.runtime.id,
    isAllowedUrl,
    isAppUrl,
  );
  if (!allowed) {
    return false;
  }

  if (message.type === "schedule-observation") {
    void chrome.storage.session.set({
      latestObservation: message.payload,
      latestObservationAt: Date.now(),
    });
    void chrome.tabs.create({ url: chrome.runtime.getURL("dist/preview.html") });
    return false;
  }

  // 自动提取（EXT-B11）：课表页加载后 content script 自动回传；
  // 存起来并打开 App 导入页，等 App 桥接脚本拉取。若用户刚手动点击过
  // （60 秒内已有观察值，预览页流程已启动），忽略自动结果避免双开。
  if (message.type === "schedule-auto-observation") {
    void (async () => {
      const stored = (await chrome.storage.session.get(["latestObservationAt"])) as {
        latestObservationAt?: number;
      };
      if (stored.latestObservationAt && Date.now() - stored.latestObservationAt < 60_000) {
        return;
      }
      await chrome.storage.session.set({
        latestAutoObservation: message.payload,
        latestObservationAt: Date.now(),
      });
      await chrome.tabs.create({ url: `${APP_ORIGINS[0]}${APP_IMPORT_PATH}?source=eamis-auto` });
    })();
    return false;
  }

  // App 导入页桥接：页面就绪后把暂存的自动观察值交给它（只回传一次）
  if (message.type === "app-bridge-ready") {
    void (async () => {
      const stored = (await chrome.storage.session.get(["latestAutoObservation"])) as {
        latestAutoObservation?: unknown;
      };
      if (stored.latestAutoObservation) {
        await chrome.storage.session.remove("latestAutoObservation");
        sendResponse({ ok: true, observation: stored.latestAutoObservation });
      } else {
        sendResponse({ ok: false });
      }
    })();
    return true;
  }

  if (message.type === "submit-confirmed-draft") {
    void (async () => {
      const stored = (await chrome.storage.session.get("importTicket")) as {
        importTicket?: ImportTicket;
      };
      if (!stored.importTicket) {
        sendResponse({ ok: false, error: "NO_TICKET" });
        return;
      }
      try {
        const payload = message.payload as { timetable: unknown };
        const result = await submitConfirmedDraft(
          stored.importTicket,
          stored.importTicket.workspaceRef,
          payload.timetable,
          { backendOrigin: BACKEND_ORIGIN },
        );
        await chrome.storage.session.remove("importTicket");
        sendResponse({ ok: true, data: result });
      } catch (error) {
        sendResponse({ ok: false, error: (error as { code?: string }).code ?? "UNKNOWN" });
      }
    })();
    return true;
  }

  return false;
});
