import type { PageObservation, TimetableImport } from "@campus/import-core";

/**
 * 扩展独立预览页：用户确认只发生在这里。
 *
 * - 数据只来自 chrome.storage.session 中本扩展写入的观察值；
 * - 所有文本用 textContent 渲染，不插入用户 HTML、不加载远程资源；
 * - 确认后由 service worker 用短期票据提交；也支持离线 JSON 导出作为持久降级。
 */

declare const chrome: typeof globalThis.chrome;

export function renderObservation(observation: PageObservation, parsed: TimetableImport | null): void {
  const summary = document.querySelector("#summary");
  if (summary) {
    summary.textContent = parsed
      ? `共 ${parsed.courses.length} 门课程；覆盖范围：${parsed.source.coverage.scope}（${parsed.source.coverage.completeness}）`
      : "解析失败或页面不支持，请改用文件导入。";
  }
  const table = document.querySelector("#courses");
  if (table && parsed) {
    table.textContent = "";
    for (const course of parsed.courses) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.textContent = course.title;
      row.appendChild(cell);
      table.appendChild(row);
    }
  }
}

export function exportOfflineJson(payload: TimetableImport): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "timetable-import.json";
  anchor.click();
  URL.revokeObjectURL(url);
}
