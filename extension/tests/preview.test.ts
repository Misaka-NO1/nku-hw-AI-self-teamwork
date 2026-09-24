// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";

import { initPreview, renderObservation } from "../src/preview/preview";
import type { PageObservation } from "@campus/import-core";

const observation: PageObservation = {
  origin: "https://fixtures.example.invalid",
  pathname: "/demo/timetable",
  frameOrigin: null,
  tableHeaders: ["课程", "星期", "节次", "周次"],
  rows: [["高等数学（虚构）", "周一", "1-2", "1-4"]],
  selectedTerm: null,
  selectedWeeks: [],
  hasPagination: false,
  hasVirtualRows: false,
};

function mockChrome(stored: Record<string, unknown>) {
  const sendMessage = vi.fn().mockResolvedValue({ ok: true });
  const chromeApi = {
    runtime: { id: "ext-id", sendMessage },
    storage: {
      session: {
        get: vi.fn().mockResolvedValue(stored),
      },
    },
  } as unknown as typeof chrome;
  return { chromeApi, sendMessage };
}

describe("预览页启动入口（PR #2 审核意见 2）", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <main id="app">
        <section id="summary"></section>
        <table id="courses"></table>
        <button id="export-json" type="button">导出 JSON</button>
        <button id="submit-draft" type="button">确认并创建草稿</button>
      </main>`;
  });

  it("读取 session 中的观察值并渲染课程行", async () => {
    const { chromeApi } = mockChrome({ latestObservation: observation });
    await initPreview(chromeApi);
    expect(document.querySelector("#summary")!.textContent).toContain("1 行课程数据");
    expect(document.querySelectorAll("#courses tr")).toHaveLength(1);
    expect(document.querySelector("#courses")!.textContent).toContain("高等数学（虚构）");
  });

  it("没有解析结果时提交按钮禁用，不表现为可用", async () => {
    const { chromeApi, sendMessage } = mockChrome({ latestObservation: observation });
    await initPreview(chromeApi);
    const submit = document.querySelector<HTMLButtonElement>("#submit-draft")!;
    expect(submit.disabled).toBe(true);
    expect(submit.textContent).toContain("需先关联学期日历");
    submit.click();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("没有观察值时给出明确提示", async () => {
    const { chromeApi } = mockChrome({});
    await initPreview(chromeApi);
    expect(document.querySelector("#summary")!.textContent).toContain("没有待预览的课表数据");
  });

  it("renderObservation 只写 textContent，不插入 HTML", () => {
    renderObservation(
      { ...observation, rows: [["<img src=x onerror=alert(1)>", "周一", "1-2", "1-4"]] },
      null,
    );
    expect(document.querySelector("#courses img")).toBeNull();
    expect(document.querySelector("#courses")!.textContent).toContain("<img");
  });
});
