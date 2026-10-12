import { DEGREE_PLAN_URL, extractDegreePlanFromDoc, degreeProgressForStorage } from "@campus/import-core";

/** Same MV3 extension; only the completion report, never the separate grade/account page. */
export function registerDegreeContent(chromeApi: typeof chrome, doc: Document, pageUrl: string,
  options: { getPageUrl?: () => string; registerListener?: boolean } = {}) {
  const url = new URL(pageUrl);
  if (url.origin + url.pathname !== DEGREE_PLAN_URL || doc.querySelector('input[type="password"]') || doc.getElementById("campus-degree-import-host")) return;
  let notify = (_text: string) => {};
  function download() {
    const currentUrl = options.getPageUrl?.() ?? pageUrl;
    const current = new URL(currentUrl);
    if (current.origin + current.pathname !== DEGREE_PLAN_URL) throw new Error("当前不是计划完成情况页，请返回该页面导出");
    const payload = degreeProgressForStorage(extractDegreePlanFromDoc(doc, currentUrl));
    const href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" }));
    const link = doc.createElement("a"); link.href = href; link.download = "degree-progress.json";
    doc.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(href), 1000);
    notify(`已导出 ${payload.modules.length} 个分类。把 degree-progress.json 发给南开 Agent 核对，确认后保存。不含课程成绩、姓名或学号；未自动上传。`);
    return payload;
  }
  if (options.registerListener !== false) chromeApi.runtime.onMessage.addListener((raw, sender, respond) => {
    if (sender.id !== chromeApi.runtime.id || raw?.type !== "extract-visible-degree-plan") return false;
    try { download(); respond({ ok: true }); }
    catch (error) { const message = error instanceof Error ? error.message : "导出失败"; notify(message); respond({ ok: false, error: message }); }
    return false;
  });
  const host = doc.createElement("div"); host.id = "campus-degree-import-host";
  const shadow = host.attachShadow({ mode: "closed" });
  const style = doc.createElement("style"); style.textContent = ':host{all:initial}div{position:fixed;right:24px;bottom:24px;z-index:2147483647;font:14px system-ui;max-width:280px}button{padding:12px 20px;border:0;border-radius:24px;color:white;background:#196577;cursor:pointer}p{background:#fff;padding:8px;border:1px solid #ccc;color:#123}';
  const wrap = doc.createElement("div"), button = doc.createElement("button"), message = doc.createElement("p");
  message.setAttribute("aria-live", "polite");
  notify = text => { message.hidden = false; message.textContent = text; };
  button.type = "button"; button.textContent = "导出计划完成情况 JSON"; message.hidden = true;
  button.onclick = async () => {
    button.disabled = true; message.hidden = false; message.textContent = "正在读取计划完成情况…";
    try { download(); }
    catch (error) { message.textContent = error instanceof Error ? error.message : "提取失败"; }
    finally { button.disabled = false; }
  };
  wrap.append(button, message); shadow.append(style, wrap); doc.body.append(host);
}
