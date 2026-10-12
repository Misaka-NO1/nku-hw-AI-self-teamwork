import { isExtractionAllowed, PRODUCTION_WHITELIST, DEV_FIXTURE_WHITELIST, BACKEND_ORIGIN, APP_ORIGINS, APP_IMPORT_PATH, APP_DEGREE_PATH, isAppUrl, isDegreePageUrl } from "./config";
import { validateDegreePlanImport } from "@campus/import-core";
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
  if (tab.id === undefined || !tab.url || (!isAllowedUrl(tab.url) && !isDegreePageUrl(tab.url))) {
    // EXT-01：非白名单域名不注入、不解析、不上传
    return;
  }
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["dist/eamis-content.js"],
  });
  chrome.tabs.sendMessage(tab.id, { type: isDegreePageUrl(tab.url) ? "extract-visible-degree-plan" : "extract-visible-schedule", payload: null });
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
    isDegreePageUrl,
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
  if (message.type === "schedule-auto-observation" || message.type === "degree-plan-observation") {
    void (async () => {
      const degree = message.type === "degree-plan-observation";
      const observation = degree ? validateDegreePlanImport(message.payload) : message.payload;
      const destination = degree ? APP_DEGREE_PATH : APP_IMPORT_PATH;
      const transferId=crypto.randomUUID();
      await chrome.storage.session.set({
        [`transfer:${transferId}`]: {observation, destination, expiresAt:Date.now()+600_000},
      });
      await chrome.tabs.create({ url: `${APP_ORIGINS[0]}${destination}?source=eamis-auto&transfer_id=${transferId}` });
      sendResponse({ok:true});
    })().catch(()=>sendResponse({ok:false,error:"IMPORT_OPEN_FAILED"}));
    return true;
  }

  // App 导入页桥接：页面就绪后把暂存的自动观察值交给它（只回传一次）
  if (message.type === "app-bridge-ready") {
    void (async () => {
      const appUrl=new URL(sender.url ?? sender.tab?.url ?? "");
      const transferId=appUrl.searchParams.get("transfer_id");
      if(!transferId || !/^[a-f0-9-]{36}$/.test(transferId)){sendResponse({ok:false});return;}
      const key=`transfer:${transferId}`;
      const stored=await chrome.storage.session.get(key);
      const item=stored[key] as {observation:unknown;destination?:string;expiresAt:number}|undefined;
      if (item && item.expiresAt>Date.now() && appUrl.pathname === (item.destination ?? APP_IMPORT_PATH)) {
        await chrome.storage.session.remove(key);
        sendResponse({ ok: true, observation: item.observation });
      } else {
        sendResponse({ ok: false });
      }
    })().catch(()=>sendResponse({ok:false}));
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
