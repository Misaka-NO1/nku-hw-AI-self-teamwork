// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

import { extractCourseObservation, registerContentListener } from "../src/content";

type Listener = (
  raw: unknown,
  sender: unknown,
  sendResponse: (response: unknown) => void,
) => boolean;

function mockChrome() {
  const listeners: Listener[] = [];
  const sendMessage = vi.fn().mockResolvedValue(undefined);
  const chromeApi = {
    runtime: {
      id: "ext-id",
      onMessage: { addListener: (fn: Listener) => listeners.push(fn) },
      sendMessage,
    },
  } as unknown as typeof chrome;
  return { chromeApi, listeners, sendMessage };
}

describe("content script 消息入口（PR #2 审核意见 2）", () => {
  it("收到 extract-visible-schedule 后提取并回传 schedule-observation", () => {
    document.body.innerHTML = `
      <table>
        <tr><th>课程</th><th>星期</th><th>节次</th><th>周次</th></tr>
        <tr><td>高等数学（虚构）</td><td>周一</td><td>1-2</td><td>1-4</td></tr>
      </table>`;
    const { chromeApi, listeners, sendMessage } = mockChrome();
    registerContentListener(chromeApi, document, "https://fixtures.example.invalid/demo/timetable");
    expect(listeners).toHaveLength(1);

    const sendResponse = vi.fn();
    listeners[0]({ type: "extract-visible-schedule", payload: null }, {}, sendResponse);
    expect(sendResponse).toHaveBeenCalledWith({ ok: true });
    expect(sendMessage).toHaveBeenCalledTimes(1);
    const sent = sendMessage.mock.calls[0][0] as { type: string; payload: { rows: string[][] } };
    expect(sent.type).toBe("schedule-observation");
    expect(sent.payload.rows).toEqual([["高等数学（虚构）", "周一", "1-2", "1-4"]]);
  });

  it("页面结构不符合预期时回传 UNSUPPORTED_PAGE 结构化错误", () => {
    document.body.innerHTML = "<div>页面已改版</div>";
    const { chromeApi, listeners, sendMessage } = mockChrome();
    registerContentListener(chromeApi, document, "https://fixtures.example.invalid/demo/timetable");

    const sendResponse = vi.fn();
    listeners[0]({ type: "extract-visible-schedule", payload: null }, {}, sendResponse);
    expect(sendMessage).not.toHaveBeenCalled();
    const response = sendResponse.mock.calls[0][0] as {
      ok: boolean;
      error: { code: string; fallback: string };
    };
    expect(response.ok).toBe(false);
    expect(response.error.code).toBe("UNSUPPORTED_PAGE");
    expect(response.error.fallback).toContain("文件导入");
  });

  it("忽略非提取消息与畸形消息", () => {
    document.body.innerHTML = "";
    const { chromeApi, listeners } = mockChrome();
    registerContentListener(chromeApi, document, "https://fixtures.example.invalid/demo/timetable");
    const sendResponse = vi.fn();
    expect(listeners[0]({ type: "submit-confirmed-draft", payload: {} }, {}, sendResponse)).toBe(false);
    expect(listeners[0]("garbage", {}, sendResponse)).toBe(false);
    expect(sendResponse).not.toHaveBeenCalled();
  });

  it("extractCourseObservation 不读取认证字段", () => {
    document.body.innerHTML = `
      <input type="password" value="secret">
      <table>
        <tr><th>课程</th><th>星期</th><th>节次</th><th>周次</th></tr>
        <tr><td>数学</td><td>周一</td><td>1-2</td><td>1-4</td></tr>
      </table>`;
    const observation = extractCourseObservation(document, {
      pageUrl: "https://fixtures.example.invalid/demo/timetable",
    });
    expect(JSON.stringify(observation)).not.toContain("secret");
  });
});
