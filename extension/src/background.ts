import { isExtractionAllowed, PRODUCTION_WHITELIST, DEV_FIXTURE_WHITELIST, BACKEND_ORIGIN } from "./config";
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
  );
  if (!allowed) {
    return false;
  }

  if (message.type === "schedule-observation") {
    void chrome.storage.session.set({ latestObservation: message.payload });
    void chrome.tabs.create({ url: chrome.runtime.getURL("dist/preview.html") });
    return false;
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
