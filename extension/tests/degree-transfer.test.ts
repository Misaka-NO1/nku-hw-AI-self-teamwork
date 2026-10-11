// @vitest-environment jsdom
/**
 * degree-transfer / degree-app-bridge 独立测试（不依赖 background / manifest）。
 *
 * 覆盖：来源扩展 id 与页面精确 origin+path 校验、payload 畸形/超限/身份字段、
 * 一次性与十分钟过期、课表链路消息不被处理、桥接不消费课表 transfer、
 * 以及工具站桥接只派发观察值本身。
 */
import { describe, expect, it, vi } from "vitest";

import { APP_ORIGINS } from "../src/config";
import {
  degreeTransferKey,
  DEGREE_BRIDGE_READY_MESSAGE,
  DEGREE_SOURCE_URL,
  DEGREE_TABLE_HEADERS,
  DEGREE_TOOL_PATH,
  DEGREE_TRANSFER_KEY_PREFIX,
  DEGREE_TRANSFER_TTL_MS,
  buildDegreeToolUrl,
  handleDegreeMessage,
  type DegreeMessageSender,
  type DegreeTransferChromeApi,
  type DegreeTransferResponse,
} from "../src/degree-transfer";
import {
  DEGREE_IMPORT_READY_EVENT,
  DEGREE_READ_ERROR_EVENT,
  DEGREE_OBSERVATION_EVENT,
  registerDegreeAppBridge,
  type DegreeBridgeChromeApi,
} from "../src/degree-app-bridge";

const EXTENSION_ID = "test-extension-id";
const PAGE_URL = DEGREE_SOURCE_URL;
const TIMETABLE_URL = "https://eamis.nankai.edu.cn/eams/courseTableForStd";
const TOOL_ORIGIN = APP_ORIGINS[0];
const TRANSFER_ID = "11111111-2222-4333-8444-555555555555";
const NOW = Date.parse("2026-02-01T00:00:00.000Z");

function toolUrl(transferId: string = TRANSFER_ID): string {
  return `${TOOL_ORIGIN}${DEGREE_TOOL_PATH}?degree_transfer_id=${transferId}`;
}

function validSource(): Record<string, unknown> {
  return {
    url: DEGREE_SOURCE_URL,
    captured_at: "2026-02-01T00:00:00.000Z",
    coverage: "unknown",
    adapter_verified: false,
  };
}

function validObservation(): Record<string, unknown> {
  return {
    kind: "degree-table-observation",
    source: validSource(),
    headers: [...DEGREE_TABLE_HEADERS],
    rows: [{ cells: ["1", "高等数学", "5", "5", "90", "是", ""], locator: "table-row:2" }],
  };
}

function degreeObservationMessage(payload: unknown = validObservation()): {
  type: string;
  payload: unknown;
} {
  return { type: "degree-observation", payload };
}

function sender(overrides: Partial<DegreeMessageSender> = {}): DegreeMessageSender {
  return { id: EXTENSION_ID, url: PAGE_URL, tab: { url: PAGE_URL }, ...overrides };
}

function createChromeApi() {
  const store = new Map<string, unknown>();
  const createdTabs: string[] = [];
  const get = vi.fn(async (key: string) => (store.has(key) ? { [key]: store.get(key) } : {}));
  const set = vi.fn(async (items: Record<string, unknown>) => {
    for (const [key, value] of Object.entries(items)) store.set(key, value);
  });
  const remove = vi.fn(async (key: string) => {
    store.delete(key);
  });
  const create = vi.fn(async (props: { url: string }) => {
    createdTabs.push(props.url);
    return { id: createdTabs.length };
  });
  const api: DegreeTransferChromeApi = {
    runtime: { id: EXTENSION_ID },
    storage: { session: { get, set, remove } },
    tabs: { create },
  };
  return { api, store, createdTabs, remove, set };
}

interface RouteOutcome {
  handled: boolean;
  response: DegreeTransferResponse;
}

async function dispatch(
  raw: unknown,
  from: DegreeMessageSender,
  chrome: ReturnType<typeof createChromeApi>,
): Promise<RouteOutcome> {
  const route = handleDegreeMessage(raw, from, chrome.api, {
    now: () => NOW,
    randomUUID: () => TRANSFER_ID,
  });
  if (!route.handled) return { handled: false, response: { ok: false, error: "NOT_HANDLED" } };
  return { handled: true, response: await route.response };
}

async function flushAsyncWork(): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(() => resolve(), 0));
}

describe("degree-transfer 并发和临时记录完整性", () => {
  it("并发领取只能一方取得观察值", async () => {
    const chrome = createChromeApi();
    await dispatch(degreeObservationMessage(), sender(), chrome);
    const from = sender({ url: toolUrl(), tab: { url: toolUrl() } });
    const results = await Promise.all([dispatch({ type: "degree-bridge-ready", payload: null }, from, chrome),
      dispatch({ type: "degree-bridge-ready", payload: null }, from, chrome)]);
    expect(results.filter(result => result.response.ok)).toHaveLength(1);
  });
  it.each([NaN, Infinity, NOW + DEGREE_TRANSFER_TTL_MS + 1])("拒绝非法有效期 %s", async expiresAt => {
    const chrome = createChromeApi();
    chrome.store.set(degreeTransferKey(TRANSFER_ID), { observation: validObservation(), expiresAt });
    const result = await dispatch({ type: "degree-bridge-ready", payload: null }, sender({ url: toolUrl() }), chrome);
    expect(result.response.ok).toBe(false);
    expect(chrome.store.has(degreeTransferKey(TRANSFER_ID))).toBe(false);
  });
  it("重新校验临时数据，拒绝被污染的记录", async () => {
    const chrome = createChromeApi();
    chrome.store.set(degreeTransferKey(TRANSFER_ID), { observation: { private: "untrusted" }, expiresAt: NOW + 1000 });
    const result = await dispatch({ type: "degree-bridge-ready", payload: null }, sender({ url: toolUrl() }), chrome);
    expect(result.response.ok).toBe(false);
  });
});

describe("degree-transfer：合法链路与目标地址", () => {
  it("合法观察值写入 degree-transfer:<uuid> 并打开固定工具站", async () => {
    const chrome = createChromeApi();
    const outcome = await dispatch(degreeObservationMessage(), sender(), chrome);

    expect(outcome.handled).toBe(true);
    const response = outcome.response;
    expect(response.ok).toBe(true);
    if (!response.ok) return;
    expect(response.transferId).toBe(TRANSFER_ID);
    expect(response.expiresAt).toBe(NOW + DEGREE_TRANSFER_TTL_MS);

    expect([...chrome.store.keys()]).toEqual([`${DEGREE_TRANSFER_KEY_PREFIX}${TRANSFER_ID}`]);
    expect(chrome.createdTabs).toHaveLength(1);

    const opened = new URL(chrome.createdTabs[0]);
    expect(opened.origin).toBe(TOOL_ORIGIN);
    expect(opened.pathname).toBe(DEGREE_TOOL_PATH);
    expect(opened.searchParams.get("degree_transfer_id")).toBe(TRANSFER_ID);
    expect([...opened.searchParams.keys()]).toEqual(["degree_transfer_id"]);
  });

  it("buildDegreeToolUrl 只接受 uuid 且指向固定工具站", () => {
    const url = new URL(buildDegreeToolUrl(TRANSFER_ID));
    expect(url.origin).toBe(TOOL_ORIGIN);
    expect(url.pathname).toBe(DEGREE_TOOL_PATH);
    expect(url.searchParams.get("degree_transfer_id")).toBe(TRANSFER_ID);

    expect(() => buildDegreeToolUrl("../../evil")).toThrowError();
    expect(() => buildDegreeToolUrl("")).toThrowError();
  });
});

describe("degree-transfer：来源校验", () => {
  it("扩展 id 不匹配时拒绝，不写入也不打开页面", async () => {
    const chrome = createChromeApi();
    const outcome = await dispatch(
      degreeObservationMessage(),
      sender({ id: "other-extension-id" }),
      chrome,
    );

    expect(outcome.handled).toBe(true);
    expect(outcome.response).toEqual({ ok: false, error: "SENDER_REJECTED" });
    expect(chrome.store.size).toBe(0);
    expect(chrome.createdTabs).toHaveLength(0);
    expect(chrome.set).not.toHaveBeenCalled();
  });

  it("来源页面必须是精确的 origin+path", async () => {
    const badUrls = [
      TIMETABLE_URL,
      "https://example.com/eams/myPlanCompl.action",
      "http://eamis.nankai.edu.cn/eams/myPlanCompl.action",
      "https://eamis.nankai.edu.cn/eams/myPlanCompl.action/extra",
      "https://eamis.nankai.edu.cn/eams/myPlanCompl",
    ];
    for (const url of badUrls) {
      const chrome = createChromeApi();
      const outcome = await dispatch(
        degreeObservationMessage(),
        sender({ url, tab: { url } }),
        chrome,
      );
      expect(outcome.response).toEqual({ ok: false, error: "SENDER_REJECTED" });
      expect(chrome.store.size).toBe(0);
      expect(chrome.createdTabs).toHaveLength(0);
    }
  });

  it("sender.url 缺失或与 sender.tab.url 不一致时拒绝", async () => {
    const missing = await dispatch(degreeObservationMessage(), { id: EXTENSION_ID }, createChromeApi());
    expect(missing.response).toEqual({ ok: false, error: "SENDER_REJECTED" });

    const mismatch = await dispatch(
      degreeObservationMessage(),
      sender({ tab: { url: TIMETABLE_URL } }),
      createChromeApi(),
    );
    expect(mismatch.response).toEqual({ ok: false, error: "SENDER_REJECTED" });

    const tabOnly = await dispatch(
      degreeObservationMessage(),
      { id: EXTENSION_ID, tab: { url: PAGE_URL } },
      createChromeApi(),
    );
    expect(tabOnly.response).toEqual({ ok: false, error: "SENDER_REJECTED" });
  });
});

describe("degree-transfer：payload 校验", () => {
  const cases: { name: string; payload: unknown; code: string }[] = [
    { name: "非对象", payload: null, code: "MALFORMED_DEGREE_PAYLOAD" },
    {
      name: "kind 不符",
      payload: { ...validObservation(), kind: "page-observation" },
      code: "UNEXPECTED_DEGREE_KIND",
    },
    {
      name: "source.url 带查询串",
      payload: { ...validObservation(), source: { ...validSource(), url: `${DEGREE_SOURCE_URL}?planId=1` } },
      code: "UNEXPECTED_DEGREE_SOURCE_URL",
    },
    {
      name: "source.url 换域名",
      payload: { ...validObservation(), source: { ...validSource(), url: "https://example.com/eams/myPlanCompl.action" } },
      code: "UNEXPECTED_DEGREE_SOURCE_URL",
    },
    {
      name: "声称已核查",
      payload: { ...validObservation(), source: { ...validSource(), adapter_verified: true } },
      code: "DEGREE_ADAPTER_STATE_INVALID",
    },
    {
      name: "声称完整覆盖",
      payload: { ...validObservation(), source: { ...validSource(), coverage: "partial" } },
      code: "DEGREE_ADAPTER_STATE_INVALID",
    },
    {
      name: "表头缺失",
      payload: { ...validObservation(), headers: DEGREE_TABLE_HEADERS.slice(0, 3) },
      code: "UNSUPPORTED_DEGREE_HEADERS",
    },
    { name: "空 rows", payload: { ...validObservation(), rows: [] }, code: "EMPTY_DEGREE_ROWS" },
    {
      name: "单元格非字符串",
      payload: { ...validObservation(), rows: [{ cells: [1, 2], locator: "table-row:2" }] },
      code: "MALFORMED_DEGREE_CELL",
    },
    {
      name: "row 缺 locator",
      payload: { ...validObservation(), rows: [{ cells: ["1"] }] },
      code: "MALFORMED_DEGREE_ROW",
    },
    {
      name: "身份字段",
      payload: {
        ...validObservation(),
        rows: [{ cells: ["1", "高等数学", "5", "5", "90", "是", "学号：2021001"], locator: "table-row:2" }],
      },
      code: "IDENTITY_IN_DEGREE_PAYLOAD",
    },
    {
      name: "身份字段藏在额外键里",
      payload: { ...validObservation(), studentName: "姓名：张三" },
      code: "IDENTITY_IN_DEGREE_PAYLOAD",
    },
  ];

  for (const testCase of cases) {
    it(`拒绝 ${testCase.name}`, async () => {
      const chrome = createChromeApi();
      const outcome = await dispatch(degreeObservationMessage(testCase.payload), sender(), chrome);
      expect(outcome.handled).toBe(true);
      expect(outcome.response).toEqual({ ok: false, error: testCase.code });
      expect(chrome.store.size).toBe(0);
      expect(chrome.createdTabs).toHaveLength(0);
    });
  }

  it("payload 超过大小上限时拒绝", async () => {
    const payload = { ...validObservation(), filler: "x".repeat(1_100_000) };
    const outcome = await dispatch(degreeObservationMessage(payload), sender(), createChromeApi());
    expect(outcome.response).toEqual({ ok: false, error: "DEGREE_PAYLOAD_TOO_LARGE" });
  });

  it("行数超过上限时拒绝", async () => {
    const rows = Array.from({ length: 2001 }, (_value, index) => ({
      cells: ["1"],
      locator: `table-row:${index + 2}`,
    }));
    const outcome = await dispatch(
      degreeObservationMessage({ ...validObservation(), rows }),
      sender(),
      createChromeApi(),
    );
    expect(outcome.response).toEqual({ ok: false, error: "DEGREE_TABLE_TOO_LARGE" });
  });
});

describe("degree-transfer：一次性与过期", () => {
  it("bridge-ready 只成功一次", async () => {
    const chrome = createChromeApi();
    await dispatch(degreeObservationMessage(), sender(), chrome);

    const first = await dispatch(
      { type: DEGREE_BRIDGE_READY_MESSAGE, payload: null },
      sender({ url: toolUrl(), tab: { url: toolUrl() } }),
      chrome,
    );
    expect(first.response.ok).toBe(true);
    if (first.response.ok) {
      expect(first.response.observation).toEqual(validObservation());
    }

    const second = await dispatch(
      { type: DEGREE_BRIDGE_READY_MESSAGE, payload: null },
      sender({ url: toolUrl(), tab: { url: toolUrl() } }),
      chrome,
    );
    expect(second.response).toEqual({ ok: false, error: "NO_DEGREE_TRANSFER" });
    expect(chrome.store.size).toBe(0);
  });

  it("超过十分钟的票据被拒绝并清除", async () => {
    const chrome = createChromeApi();
    const key = `${DEGREE_TRANSFER_KEY_PREFIX}${TRANSFER_ID}`;
    chrome.store.set(key, { observation: validObservation(), expiresAt: NOW - 1 });

    const outcome = await dispatch(
      { type: DEGREE_BRIDGE_READY_MESSAGE, payload: null },
      sender({ url: toolUrl(), tab: { url: toolUrl() } }),
      chrome,
    );
    expect(outcome.response).toEqual({ ok: false, error: "DEGREE_TRANSFER_EXPIRED" });
    expect(chrome.remove).toHaveBeenCalledWith(key);
    expect(chrome.store.size).toBe(0);
  });

  it("bridge-ready 来源必须是固定工具站 origin+path，且必须带 uuid", async () => {
    const badUrls = [
      `${TOOL_ORIGIN}/tools/import?degree_transfer_id=${TRANSFER_ID}`,
      `https://evil.example/tools/degree?degree_transfer_id=${TRANSFER_ID}`,
      `${TOOL_ORIGIN}/tools/degree/extra?degree_transfer_id=${TRANSFER_ID}`,
      `${TOOL_ORIGIN}/tools/degree`,
      `${TOOL_ORIGIN}/tools/degree?degree_transfer_id=not-a-uuid`,
    ];
    for (const url of badUrls) {
      const chrome = createChromeApi();
      chrome.store.set(`${DEGREE_TRANSFER_KEY_PREFIX}${TRANSFER_ID}`, {
        observation: validObservation(),
        expiresAt: NOW + DEGREE_TRANSFER_TTL_MS,
      });
      const outcome = await dispatch(
        { type: DEGREE_BRIDGE_READY_MESSAGE, payload: null },
        sender({ url, tab: { url } }),
        chrome,
      );
      expect(outcome.response.ok).toBe(false);
      expect(chrome.createdTabs).toHaveLength(0);
      // 票据没有被错误来源消费
      expect(chrome.store.size).toBe(1);
    }

    const wrongSender = await dispatch(
      { type: DEGREE_BRIDGE_READY_MESSAGE, payload: null },
      sender({ id: "other-extension-id", url: toolUrl(), tab: { url: toolUrl() } }),
      createChromeApi(),
    );
    expect(wrongSender.response).toEqual({ ok: false, error: "SENDER_REJECTED" });
  });
});

describe("degree-transfer：不处理课表链路消息", () => {
  it("课表消息与无效原始消息返回 handled=false", () => {
    const scheduledTypes = [
      "schedule-observation",
      "schedule-auto-observation",
      "app-bridge-ready",
      "submit-confirmed-draft",
      "degree-observation-extra",
    ];
    for (const type of scheduledTypes) {
      const api = createChromeApi().api;
      expect(handleDegreeMessage({ type, payload: null }, sender(), api).handled).toBe(false);
    }
    expect(handleDegreeMessage(null, sender(), createChromeApi().api).handled).toBe(false);
    expect(handleDegreeMessage({}, sender(), createChromeApi().api).handled).toBe(false);
    expect(handleDegreeMessage("degree-observation", sender(), createChromeApi().api).handled).toBe(
      false,
    );
  });

  it("degree 桥接不消费课表 transfer", async () => {
    const chrome = createChromeApi();
    const timetableKey = `transfer:${TRANSFER_ID}`;
    chrome.store.set(timetableKey, {
      observation: { kind: "page-observation" },
      expiresAt: NOW + 600_000,
    });

    const outcome = await dispatch(
      { type: DEGREE_BRIDGE_READY_MESSAGE, payload: null },
      sender({ url: toolUrl(), tab: { url: toolUrl() } }),
      chrome,
    );
    expect(outcome.response).toEqual({ ok: false, error: "NO_DEGREE_TRANSFER" });
    expect(chrome.store.has(timetableKey)).toBe(true);
    expect(chrome.remove).not.toHaveBeenCalled();
  });
});

describe("degree-app-bridge：只转发培养计划观察值", () => {
  function bridgeApi(sendMessage: (message: { type: string; payload: unknown }) => Promise<unknown>): DegreeBridgeChromeApi {
    return { runtime: { id: EXTENSION_ID, sendMessage } };
  }

  it("普通模块页无票据时不自动领取", () => {
    const win = new EventTarget() as unknown as Window;
    const sendMessage = vi.fn(async () => ({ ok: false }));
    expect(registerDegreeAppBridge(bridgeApi(sendMessage), win, `${TOOL_ORIGIN}/tools/degree`)).toBe(false);
    win.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("领取失败通知页面但不带后台原数据", async () => {
    const win = new EventTarget() as unknown as Window;
    const errors: Event[] = [];
    win.addEventListener(DEGREE_READ_ERROR_EVENT, event => errors.push(event));
    registerDegreeAppBridge(bridgeApi(async () => ({ ok: false, error: "PRIVATE_MARKER" })), win, toolUrl());
    win.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
    await flushAsyncWork();
    expect(errors).toHaveLength(1);
    expect((errors[0] as CustomEvent).detail).toBeUndefined();
  });

  it("非目标 URL 不注册、不发消息", () => {
    const win = new EventTarget() as unknown as Window;
    const sendMessage = vi.fn(async (_message: { type: string; payload: unknown }) => ({ ok: true }));

    expect(registerDegreeAppBridge(bridgeApi(sendMessage), win, `${TOOL_ORIGIN}/tools/import`)).toBe(
      false,
    );
    expect(registerDegreeAppBridge(bridgeApi(sendMessage), win, PAGE_URL)).toBe(false);
    win.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("页面就绪后发 degree-bridge-ready，并把观察值作为 detail 派发", async () => {
    const win = new EventTarget() as unknown as Window;
    const observation = validObservation();
    const sendMessage = vi.fn(async (_message: { type: string; payload: unknown }) => ({
      ok: true,
      observation,
      transferId: TRANSFER_ID,
    }));
    const received: unknown[] = [];
    win.addEventListener(DEGREE_OBSERVATION_EVENT, (event) => {
      received.push((event as CustomEvent).detail);
    });

    expect(registerDegreeAppBridge(bridgeApi(sendMessage), win, toolUrl())).toBe(true);
    // 重复注册不会重复监听
    expect(registerDegreeAppBridge(bridgeApi(sendMessage), win, toolUrl())).toBe(false);
    expect(sendMessage).not.toHaveBeenCalled();

    win.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
    await flushAsyncWork();

    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledWith({ type: DEGREE_BRIDGE_READY_MESSAGE, payload: null });
    // 只传观察值本身，不透传 transferId 等其它字段
    expect(received).toEqual([observation]);
  });

  it("后台没有暂存观察值时不派发事件", async () => {
    const win = new EventTarget() as unknown as Window;
    const sendMessage = vi.fn(async (_message: { type: string; payload: unknown }) => ({
      ok: false,
      error: "NO_DEGREE_TRANSFER",
    }));
    const received: unknown[] = [];
    win.addEventListener(DEGREE_OBSERVATION_EVENT, (event) => {
      received.push((event as CustomEvent).detail);
    });

    registerDegreeAppBridge(bridgeApi(sendMessage), win, toolUrl());
    win.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
    await flushAsyncWork();

    expect(received).toEqual([]);
  });

  it("课表就绪事件不会触发培养计划桥接", async () => {
    const win = new EventTarget() as unknown as Window;
    const sendMessage = vi.fn(async (_message: { type: string; payload: unknown }) => ({ ok: true }));

    registerDegreeAppBridge(bridgeApi(sendMessage), win, toolUrl());
    win.dispatchEvent(new Event("campus:schedule-import-ready"));
    win.dispatchEvent(new Event("campus:schedule-bridge-ready"));
    await flushAsyncWork();

    expect(sendMessage).not.toHaveBeenCalled();
  });
});
