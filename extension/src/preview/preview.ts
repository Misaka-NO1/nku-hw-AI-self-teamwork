import type { PageObservation, TimetableImport } from "@campus/import-core";

/**
 * 扩展独立预览页：用户确认只发生在这里。
 *
 * - 启动时从 chrome.storage.session 读取 service worker 写入的观察值并渲染；
 * - 所有文本用 textContent 渲染，不插入用户 HTML、不加载远程资源；
 * - 确认后由 service worker 用短期票据提交；离线 JSON 导出作为持久降级。
 * - 关闭页面后未提交的数据会丢失（票据与观察值只存 session）。
 */

declare const chrome: typeof globalThis.chrome;

export function renderObservation(
  observation: PageObservation | null,
  parsed: TimetableImport | null,
): void {
  const summary = document.querySelector("#summary");
  if (summary) {
    if (observation === null) {
      summary.textContent = "没有待预览的课表数据。请先在课表页面点击扩展图标提取。";
    } else if (parsed) {
      summary.textContent = `共 ${parsed.courses.length} 门课程；覆盖范围：${parsed.source.coverage.scope}（${parsed.source.coverage.completeness}）`;
    } else {
      summary.textContent = `已提取 ${observation.rows.length} 行课程数据（尚未关联学期日历，仅显示原始星期/节次/周次）。`;
    }
  }
  const table = document.querySelector("#courses");
  if (table) {
    table.textContent = "";
    if (parsed) {
      for (const course of parsed.courses) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.textContent = course.title;
        row.appendChild(cell);
        table.appendChild(row);
      }
    } else if (observation) {
      for (const cells of observation.rows) {
        const row = document.createElement("tr");
        for (const text of cells) {
          const cell = document.createElement("td");
          cell.textContent = text;
          row.appendChild(cell);
        }
        table.appendChild(row);
      }
    }
  }
}

export function exportOfflineJson(payload: unknown, filename = "timetable-import.json"): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** 预览页启动入口：读取观察值、渲染、绑定导出与提交按钮。 */
export async function initPreview(chromeApi: typeof chrome): Promise<void> {
  const stored = (await chromeApi.storage.session.get([
    "latestObservation",
    "parsedTimetable",
  ])) as { latestObservation?: PageObservation; parsedTimetable?: TimetableImport };
  const observation = stored.latestObservation ?? null;
  const parsed = stored.parsedTimetable ?? null;
  renderObservation(observation, parsed);

  const exportButton = document.querySelector<HTMLButtonElement>("#export-json");
  exportButton?.addEventListener("click", () => {
    if (parsed ?? observation) {
      exportOfflineJson(parsed ?? observation);
    }
  });

  const submitButton = document.querySelector<HTMLButtonElement>("#submit-draft");
  if (submitButton) {
    if (!parsed) {
      // 未关联学期日历无法生成标准 TimetableImport，提交禁用而不是假成功
      submitButton.disabled = true;
      submitButton.textContent = "确认并创建草稿（需先关联学期日历）";
    } else {
      submitButton.addEventListener("click", () => {
        void chromeApi.runtime.sendMessage({
          type: "submit-confirmed-draft",
          payload: { timetable: parsed },
        });
      });
    }
  }
}

// 真实预览页环境中自动启动；单测中显式调用 initPreview
if (typeof chrome !== "undefined" && chrome.runtime?.id && typeof document !== "undefined") {
  void initPreview(chrome);
}
