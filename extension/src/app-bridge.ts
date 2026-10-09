/**
 * App 桥接 content script：只注入团队工具站的课表导入页。
 *
 * 页面加载后向 service worker 报到（app-bridge-ready）；如果后台暂存了
 * 教务页自动提取的观察值，就把它作为窗口事件派发给 App：
 *   window.dispatchEvent(new CustomEvent("campus:schedule-observation", { detail }))
 * App 的导入页监听该事件后本地解析（不联网、不上传）。
 *
 * 桥接脚本自身不做任何解析，也不向页面暴露扩展能力；观察值来自已过白名单
 * 校验的教务 content script，且只回传一次。
 */

export const APP_OBSERVATION_EVENT = "campus:schedule-observation";

export function registerAppBridge(chromeApi: typeof chrome, win: Window): void {
  // React announces readiness after installing its receive listener. Don't
  // consume the one-shot transfer at document_idle before React mounts.
  win.addEventListener("campus:schedule-import-ready", () => {
  void chromeApi.runtime
    .sendMessage({ type: "app-bridge-ready", payload: null })
    .then((response: unknown) => {
      const result = response as { ok?: boolean; observation?: unknown } | undefined;
      if (!result?.ok || result.observation === undefined || result.observation === null) {
        return;
      }
      win.dispatchEvent(
        new CustomEvent(APP_OBSERVATION_EVENT, { detail: result.observation }),
      );
    })
    .catch(() => {
      // 没有暂存观察值或后台不可用：静默，用户仍可手动导入文件
    });
  }, {once:true});
  // Either React or document_idle may load first. Both sides announce readiness
  // after registering listeners; the transfer is consumed only once.
  win.dispatchEvent(new Event("campus:schedule-bridge-ready"));
}

if (typeof chrome !== "undefined" && chrome.runtime?.id) {
  registerAppBridge(chrome, window);
}
