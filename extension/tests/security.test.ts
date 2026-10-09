import { describe, expect, it } from "vitest";

import { DEV_FIXTURE_WHITELIST, isExtractionAllowed, PRODUCTION_WHITELIST } from "../src/config";
import { isSenderAllowed, parseMessage } from "../src/messages";

describe("EXT-01 非白名单域名不注入", () => {
  it("生产白名单为空：任何真实页面都不允许", () => {
    expect(isExtractionAllowed("https://eamis.nankai.edu.cn/anything", PRODUCTION_WHITELIST)).toBe(false);
    expect(isExtractionAllowed("https://any.example.com/", PRODUCTION_WHITELIST)).toBe(false);
  });

  it("开发白名单只允许精确 origin + path", () => {
    expect(isExtractionAllowed("https://fixtures.example.invalid/demo/timetable", DEV_FIXTURE_WHITELIST)).toBe(true);
    expect(isExtractionAllowed("https://evil.invalid/demo/timetable", DEV_FIXTURE_WHITELIST)).toBe(false);
    expect(isExtractionAllowed("https://fixtures.example.invalid/other", DEV_FIXTURE_WHITELIST)).toBe(false);
  });

  it("畸形 URL 不注入", () => {
    expect(isExtractionAllowed("not-a-url", DEV_FIXTURE_WHITELIST)).toBe(false);
  });
});

describe("消息协议安全", () => {
  it("拒绝未知消息类型与超大 payload", () => {
    expect(parseMessage({ type: "steal-cookies", payload: null })).toBeNull();
    expect(parseMessage("string")).toBeNull();
    expect(parseMessage({ type: "schedule-observation", payload: "x".repeat(1024 * 1024 + 1) })).toBeNull();
  });

  it("submit-confirmed-draft 只接受扩展自身预览页", () => {
    const message = { type: "submit-confirmed-draft" as const, payload: {} };
    const allow = () => true;
    expect(
      isSenderAllowed(message, { id: "ext-id", url: "chrome-extension://ext-id/preview.html" }, "ext-id", allow),
    ).toBe(true);
    // 教务页面 content script 不能发起提交（confirmed:true 无效）
    expect(
      isSenderAllowed(message, { id: "ext-id", url: "https://eamis.nankai.edu.cn/page" }, "ext-id", allow),
    ).toBe(false);
  });

  it("拒绝其他扩展伪造的消息", () => {
    const message = { type: "schedule-observation" as const, payload: {} };
    expect(
      isSenderAllowed(
        message,
        { id: "another-extension", tabUrl: "https://fixtures.example.invalid/demo/timetable" },
        "ext-id",
        () => true,
      ),
    ).toBe(false);
  });

  it("content script 的观察值必须来自白名单页面", () => {
    const message = { type: "schedule-observation" as const, payload: {} };
    const isWhitelisted = (url: string) => url.startsWith("https://fixtures.example.invalid/demo/");
    expect(
      isSenderAllowed(
        message,
        { id: "ext-id", tabUrl: "https://evil.invalid/demo/timetable" },
        "ext-id",
        isWhitelisted,
      ),
    ).toBe(false);
    expect(
      isSenderAllowed(
        message,
        { id: "ext-id", tabUrl: "https://fixtures.example.invalid/demo/timetable" },
        "ext-id",
        isWhitelisted,
      ),
    ).toBe(true);
  });
});

describe("EXT-B11 自动提取与 App 桥接消息", () => {
  it("app-bridge-ready 只接受 App origin 的页面", () => {
    const message = { type: "app-bridge-ready" as const, payload: null };
    const isApp = (url: string) => url.startsWith("http://localhost:7100");
    expect(
      isSenderAllowed(message, { id: "ext-id", url: "http://localhost:7100/" }, "ext-id", () => false, isApp),
    ).toBe(true);
    // 教务页或其他网站不能伪装 App 桥拉取暂存观察值
    expect(
      isSenderAllowed(message, { url: "https://eamis.nankai.edu.cn/eams/x" }, "ext-id", () => false, isApp),
    ).toBe(false);
    expect(
      isSenderAllowed(message, { url: "https://evil.example" }, "ext-id", () => false, isApp),
    ).toBe(false);
  });

  it("schedule-auto-observation 与手动观察值走同一白名单校验", () => {
    const message = { type: "schedule-auto-observation" as const, payload: {} };
    const whitelist = (url: string) => url.startsWith("https://eamis.nankai.edu.cn/eams/courseTableForStd");
    expect(
      isSenderAllowed(message, { id:"ext-id", tabUrl: "https://eamis.nankai.edu.cn/eams/courseTableForStd!courseTable.action" }, "ext-id", whitelist),
    ).toBe(true);
    expect(
      isSenderAllowed(message, { tabUrl: "https://evil.example" }, "ext-id", whitelist),
    ).toBe(false);
  });
});
