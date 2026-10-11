// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountDegreeButton, getMountedDegreeButton } from "../src/degree-content";
import { handleDegreeMessage, type DegreeTransferChromeApi } from "../src/degree-transfer";
import { registerDegreeAppBridge, DEGREE_IMPORT_READY_EVENT, DEGREE_OBSERVATION_EVENT } from "../src/degree-app-bridge";

describe("培养计划完整临时消息链路", () => {
  it("点击提取→来源校验→临时传递→桥接一次领取，保留课表记录", async () => {
    const sourceUrl = "https://eamis.nankai.edu.cn/eams/myPlanCompl.action";
    const extensionId = "anonymous-extension";
    const store = new Map<string, unknown>([["transfer:existing-schedule", { timetable: "unchanged" }]]);
    let openedUrl = "";
    const worker: DegreeTransferChromeApi = { runtime: { id: extensionId },
      storage: { session: { get: async key => ({ [key]: store.get(key) }),
        set: async items => { Object.entries(items).forEach(([key, value]) => store.set(key, value)); },
        remove: async key => { store.delete(key); } } },
      tabs: { create: async props => { openedUrl = props.url; } } };
    async function send(message: unknown, url: string) {
      const route = handleDegreeMessage(message, { id: extensionId, url, tab: { url } }, worker,
        { now: () => 1000, randomUUID: () => "12345678-1234-4234-8234-123456789012" });
      if (!route.handled) throw new Error("unexpected schedule routing");
      return await route.response;
    }
    const doc = document.implementation.createHTMLDocument("anonymous-degree");
    doc.body.innerHTML = `<table><tr><th>序号</th><th>课程序号</th><th>课程名称</th><th>要求学分</th><th>实修学分</th><th>成绩</th><th>是否通过</th><th>备注</th></tr>
      <tr><td colspan="3">1 虚构模块（所有子项满足）</td><td>4</td><td>2</td><td></td><td>缺2学分缺1门</td><td></td></tr>
      <tr><td>1</td><td>ANON1</td><td>虚构在读课</td><td>2</td><td>2</td><td>--</td><td>是</td><td>在读</td></tr></table>`;
    let completed!: () => void;
    const finished = new Promise<void>(resolve => { completed = resolve; });
    const content = { runtime: { id: extensionId, sendMessage: async (message: unknown) => {
      const response = await send(message, sourceUrl); completed(); return response;
    } } };
    expect(mountDegreeButton(content, doc, sourceUrl, { capturedAt: () => "2026-01-01T00:00:00Z" })).toBe(true);
    expect(openedUrl).toBe("");
    getMountedDegreeButton(doc)!.click(); await finished;
    expect(openedUrl).toContain("/tools/degree?degree_transfer_id=");
    const received: unknown[] = [];
    const receive = (event: Event) => received.push((event as CustomEvent).detail);
    window.addEventListener(DEGREE_OBSERVATION_EVENT, receive);
    try {
      let ready!: () => void;
      const bridgeDone = new Promise<void>(resolve => { ready = resolve; });
      const bridge = { runtime: { id: extensionId, sendMessage: async (message: unknown) => {
        const response = await send(message, openedUrl); ready(); return response;
      } } };
      expect(registerDegreeAppBridge(bridge, window, openedUrl)).toBe(true);
      window.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
      await bridgeDone; await Promise.resolve();
      expect(received).toHaveLength(1);
      expect(received[0]).toMatchObject({ kind: "degree-table-observation", source: { coverage: "unknown", adapter_verified: false },
        rows: [{ cells: ["1 虚构模块（所有子项满足）", "4", "2", "", "缺2学分缺1门", ""], locator: "table-row:2" },
          { cells: ["1", "ANON1", "虚构在读课", "2", "2", "--", "是", "在读"], locator: "table-row:3" }] });
      window.dispatchEvent(new Event(DEGREE_IMPORT_READY_EVENT));
      expect(received).toHaveLength(1);
      expect([...store.keys()]).toEqual(["transfer:existing-schedule"]);
      expect(store.get("transfer:existing-schedule")).toEqual({ timetable: "unchanged" });
    } finally { window.removeEventListener(DEGREE_OBSERVATION_EVENT, receive); }
  });
});
