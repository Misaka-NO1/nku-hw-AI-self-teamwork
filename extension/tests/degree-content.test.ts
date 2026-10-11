// @vitest-environment jsdom
/**
 * degree-content 独立测试（不依赖 background / manifest / 课表链路）。
 *
 * 覆盖：点击才读取、重复挂载、课表页与登录页拒绝、多候选/缺表拒绝、
 * 不猜 id 选择器、身份信息不外传、未核查状态保持。
 */
import { describe, expect, it, vi } from "vitest";

import {
  DEGREE_BUTTON_HOST_ID,
  DEGREE_OBSERVATION_MESSAGE,
  DegreeContentError,
  extractDegreeObservation,
  findUniqueDegreeTable,
  getMountedDegreeButton,
  mountDegreeButton,
  readDegreeObservationOnDemand,
  type DegreeContentChromeApi,
} from "../src/degree-content";

const PAGE_URL = "https://eamis.nankai.edu.cn/eams/myPlanCompl.action";
const TIMETABLE_URL = "https://eamis.nankai.edu.cn/eams/courseTableForStd";
const CAPTURED_AT = "2026-02-01T00:00:00.000Z";
const HEADER_CELLS = ["课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"];

type ObservationPayload = {
  kind: string;
  source: { url: string; captured_at: string; coverage: string; adapter_verified: boolean };
  headers: string[];
  rows: { cells: string[]; locator: string }[];
};

function degreeTableHtml(rows: string[][] = [["1", "高等数学", "5", "5", "90", "是", ""]]): string {
  const head = `<tr>${HEADER_CELLS.map((header) => `<th>${header}</th>`).join("")}</tr>`;
  const body = rows
    .map((cells) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("");
  return `<table><tbody>${head}${body}</tbody></table>`;
}

function createDoc(html: string): Document {
  const doc = document.implementation.createHTMLDocument("degree-fixture");
  doc.body.innerHTML = html;
  return doc;
}

function createChromeApi() {
  const sendMessage = vi.fn(async (_message: { type: string; payload: unknown }) => ({ ok: true }));
  const api: DegreeContentChromeApi = { runtime: { id: "test-extension-id", sendMessage } };
  return { api, sendMessage };
}

async function flushAsyncWork(): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(() => resolve(), 0));
}

function captureError(run: () => unknown): DegreeContentError {
  try {
    run();
  } catch (error) {
    if (error instanceof DegreeContentError) return error;
    throw error;
  }
  throw new Error("expected a DegreeContentError");
}

describe("degree-content：只有点击才读取", () => {
  it.each([undefined, null, {}, { ok: false }])("后台未明确确认时不能报告成功：%s", async response => {
    const doc = createDoc(degreeTableHtml());
    const api: DegreeContentChromeApi = { runtime: { id: "anonymous-test", sendMessage: async () => response } };
    const result = await readDegreeObservationOnDemand(api, doc, PAGE_URL, () => CAPTURED_AT);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("未成功转交");
  });
  it("挂载阶段不采集；点击按钮后才发送 degree-observation", async () => {
    const doc = createDoc(degreeTableHtml());
    const { api, sendMessage } = createChromeApi();

    expect(mountDegreeButton(api, doc, PAGE_URL, { capturedAt: () => CAPTURED_AT })).toBe(true);
    const button = getMountedDegreeButton(doc);
    if (!button) throw new Error("按钮未挂载");
    // 挂载阶段没有任何读取/外传
    expect(sendMessage).not.toHaveBeenCalled();

    button.click();
    await flushAsyncWork();

    expect(sendMessage).toHaveBeenCalledTimes(1);
    const message = sendMessage.mock.calls[0][0] as { type: string; payload: ObservationPayload };
    expect(message.type).toBe(DEGREE_OBSERVATION_MESSAGE);
    expect(message.payload.kind).toBe("degree-table-observation");
    expect(button.textContent).toContain("已读取");
  });

  it("观察值保持 adapter_verified=false / coverage=unknown，且不含身份信息", async () => {
    const doc = createDoc(degreeTableHtml([["1", "高等数学", "5", "5", "90", "是", "必修"]]));
    const { api, sendMessage } = createChromeApi();

    const result = await readDegreeObservationOnDemand(api, doc, PAGE_URL, () => CAPTURED_AT);
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.observation.kind).toBe("degree-table-observation");
    expect(result.observation.source.url).toBe(PAGE_URL);
    expect(result.observation.source.captured_at).toBe(CAPTURED_AT);
    expect(result.observation.source.coverage).toBe("unknown");
    expect(result.observation.source.adapter_verified).toBe(false);
    expect(result.observation.rows).toHaveLength(1);
    expect(result.observation.rows[0].cells).toEqual(["1", "高等数学", "5", "5", "90", "是", "必修"]);

    const payload = sendMessage.mock.calls[0][0] as { payload: unknown };
    expect(JSON.stringify(payload)).not.toMatch(/学号|姓名|身份证|密码/);
  });

  it("重复挂载不会产生第二个按钮", () => {
    const doc = createDoc(degreeTableHtml());
    const { api } = createChromeApi();

    expect(mountDegreeButton(api, doc, PAGE_URL)).toBe(true);
    expect(mountDegreeButton(api, doc, PAGE_URL)).toBe(false);
    expect(doc.querySelectorAll(`#${DEGREE_BUTTON_HOST_ID}`)).toHaveLength(1);
  });
});

describe("degree-content：非目标页面与登录页拒绝", () => {
  it("课表页 URL 拒绝挂载，也拒绝读取", () => {
    const doc = createDoc(degreeTableHtml());
    const { api, sendMessage } = createChromeApi();

    expect(mountDegreeButton(api, doc, TIMETABLE_URL)).toBe(false);
    expect(getMountedDegreeButton(doc)).toBeNull();
    expect(doc.getElementById(DEGREE_BUTTON_HOST_ID)).toBeNull();
    expect(sendMessage).not.toHaveBeenCalled();

    const error = captureError(() => extractDegreeObservation(doc, TIMETABLE_URL, CAPTURED_AT));
    expect(error.code).toBe("UNSUPPORTED_DEGREE_PAGE");
  });

  it("登录页拒绝挂载与读取，且不外传任何内容", async () => {
    const doc = createDoc(`${degreeTableHtml()}<input type="password" name="password" />`);
    const { api, sendMessage } = createChromeApi();

    expect(mountDegreeButton(api, doc, PAGE_URL)).toBe(false);
    expect(getMountedDegreeButton(doc)).toBeNull();

    const error = captureError(() => extractDegreeObservation(doc, PAGE_URL, CAPTURED_AT));
    expect(error.code).toBe("DEGREE_LOGIN_PAGE");

    const result = await readDegreeObservationOnDemand(api, doc, PAGE_URL, () => CAPTURED_AT);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("DEGREE_LOGIN_PAGE");
    expect(sendMessage).not.toHaveBeenCalled();
  });
});

describe("degree-content：只按已知表头找唯一候选表", () => {
  it("不猜 id 选择器：只有名字像培养计划的表、表头不符时仍然缺表", () => {
    const doc = createDoc(
      `<table id="myPlanComplTable"><tbody>
         <tr><th>课程号</th><th>课程名</th></tr>
         <tr><td>1</td><td>高等数学</td></tr>
       </tbody></table>`,
    );
    const error = captureError(() => findUniqueDegreeTable(doc));
    expect(error.code).toBe("DEGREE_TABLE_NOT_FOUND");
  });

  it("含无关表格时仍能定位唯一已知表头表", () => {
    const doc = createDoc(
      `<table><tbody><tr><th>序号</th><th>名称</th></tr><tr><td>1</td><td>x</td></tr></tbody></table>` +
        degreeTableHtml(),
    );
    expect(findUniqueDegreeTable(doc).tagName).toBe("TABLE");
    const observation = extractDegreeObservation(doc, PAGE_URL, CAPTURED_AT);
    expect(observation.rows).toHaveLength(1);
    expect(observation.rows[0].cells[1]).toBe("高等数学");
  });

  it("缺表时拒绝", () => {
    const doc = createDoc("<p>暂无培养计划数据</p>");
    expect(captureError(() => findUniqueDegreeTable(doc)).code).toBe("DEGREE_TABLE_NOT_FOUND");
    expect(captureError(() => extractDegreeObservation(doc, PAGE_URL, CAPTURED_AT)).code).toBe(
      "DEGREE_TABLE_NOT_FOUND",
    );
  });

  it("多候选表时拒绝", () => {
    const doc = createDoc(
      `${degreeTableHtml()}${degreeTableHtml([["2", "大学物理", "4", "4", "85", "是", ""]])}`,
    );
    expect(captureError(() => findUniqueDegreeTable(doc)).code).toBe("MULTIPLE_DEGREE_TABLES");
    expect(captureError(() => extractDegreeObservation(doc, PAGE_URL, CAPTURED_AT)).code).toBe(
      "MULTIPLE_DEGREE_TABLES",
    );
  });
});

describe("degree-content：身份信息不外传", () => {
  it("表内出现学号时拒绝读取且不发送任何消息", async () => {
    const doc = createDoc(
      degreeTableHtml([["1", "高等数学", "5", "5", "90", "是", "学号：2021001"]]),
    );
    const { api, sendMessage } = createChromeApi();

    mountDegreeButton(api, doc, PAGE_URL, { capturedAt: () => CAPTURED_AT });
    const button = getMountedDegreeButton(doc);
    if (!button) throw new Error("按钮未挂载");
    button.click();
    await flushAsyncWork();

    expect(sendMessage).not.toHaveBeenCalled();

    const result = await readDegreeObservationOnDemand(api, doc, PAGE_URL, () => CAPTURED_AT);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("IDENTITY_REGION_IN_DEGREE_TABLE");
    expect(sendMessage).not.toHaveBeenCalled();
  });
});
