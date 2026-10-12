import { mountImportButton, registerContentListener } from "./content";
import { registerDegreeContent } from "./degree-content";
import { isDegreePageUrl, isExtractionAllowed, PRODUCTION_WHITELIST } from "./config";

/** EAMIS updates its central panel/history without necessarily reloading this document. */
export function startEamisContent(chromeApi: typeof chrome, doc: Document, win: Window) {
  let degreeListening = false;
  let queued = false;
  let stopped = false;
  const currentUrl = () => win.location.href;
  const timetablePage = () => isExtractionAllowed(currentUrl(), PRODUCTION_WHITELIST);
  registerContentListener(chromeApi, doc, currentUrl(), currentUrl, timetablePage);
  const sync = () => {
    if (stopped) return;
    const degree = isDegreePageUrl(currentUrl());
    const timetable = timetablePage();
    if (!degree) doc.getElementById("campus-degree-import-host")?.remove();
    if (!timetable) doc.getElementById("campus-schedule-import-host")?.remove();
    if (doc.querySelector('input[type="password"]')) return;
    if (degree && !doc.getElementById("campus-degree-import-host")) {
      registerDegreeContent(chromeApi, doc, currentUrl(), { getPageUrl: currentUrl, registerListener: !degreeListening });
      degreeListening = true;
    }
    if (timetable) mountImportButton(chromeApi, doc, currentUrl(), {
      maxAttempts: 1, getPageUrl: currentUrl, isCurrentPage: timetablePage,
    });
  };
  const scheduleSync = () => {
    if (queued || stopped) return;
    queued = true;
    win.queueMicrotask(() => { queued = false; sync(); });
  };
  const observer = new MutationObserver(scheduleSync);
  observer.observe(doc.documentElement, { childList: true, subtree: true });
  win.addEventListener("popstate", scheduleSync);
  win.addEventListener("hashchange", scheduleSync);
  sync();
  return () => {
    stopped = true;
    observer.disconnect();
    win.removeEventListener("popstate", scheduleSync);
    win.removeEventListener("hashchange", scheduleSync);
  };
}

declare global { interface Window { __campusEamisContentStarted?: boolean } }
if (typeof chrome !== "undefined" && chrome.runtime?.id && typeof window !== "undefined"
    && !window.__campusEamisContentStarted) {
  window.__campusEamisContentStarted = true;
  startEamisContent(chrome, document, window);
}
