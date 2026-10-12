// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { startEamisContent } from "../src/eamis-content";
import { DEGREE_PLAN_URL } from "@campus/import-core";

const TIMETABLE = "https://eamis.nankai.edu.cn/eams/courseTableForStd!courseTable.action";
const plan = '<table><tr><th>课程序号</th><th>课程名称</th><th>要求学分</th><th>实修学分</th><th>成绩</th><th>是否通过</th><th>备注</th></tr><tr><td colspan="2">通识选修课</td><td>14</td><td>2</td><td colspan="3">缺学分</td></tr><tr><td>TEST001</td><td>虚构课程</td><td>2</td><td>2</td><td>通过</td><td>是</td><td></td></tr></table>';
const grid = '<input id="testSemester" value="2026-2027学年1学期"><table id="manualArrangeCourseTable"><tr><th>节次/周次</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th><th>星期六</th><th>星期日</th></tr><tr><td>第一节</td><td>虚构课表甲(0001) (某甲)(1-17,示例楼101)</td><td></td><td></td><td></td><td></td><td></td><td></td></tr></table>';
type Listener = (raw: unknown, sender: unknown, respond: (value: unknown) => void) => unknown;
let cleanup = () => {};
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = ""; });

function setup(url: string, html: string) {
  let currentUrl = url;
  const listeners: Listener[] = [];
  const sendMessage = vi.fn().mockResolvedValue({ ok: true });
  const api = { runtime: { id: "ext", sendMessage, onMessage: { addListener: (fn: Listener) => listeners.push(fn) } } } as unknown as typeof chrome;
  const roots = new WeakMap<Element, ShadowRoot>();
  const original = Element.prototype.attachShadow;
  vi.spyOn(Element.prototype, "attachShadow").mockImplementation(function (this: Element, init) {
    const shadow = original.call(this, init); roots.set(this, shadow); return shadow;
  });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const create = vi.fn().mockReturnValue("blob:test");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  document.body.innerHTML = '<main id="panel"></main>';
  const panel = document.getElementById("panel")!; panel.innerHTML = html;
  const fakeWindow = {
    location: { get href() { return currentUrl; } }, queueMicrotask,
    addEventListener: window.addEventListener.bind(window), removeEventListener: window.removeEventListener.bind(window),
  } as unknown as Window;
  cleanup = startEamisContent(api, document, fakeWindow);
  return { listeners, sendMessage, create, click, roots,
    navigate(next: string, content: string) { currentUrl = next; panel.innerHTML = content; },
    button(id: string) { return roots.get(document.getElementById(id)!)!.querySelector<HTMLButtonElement>("button")!; },
  };
}

it("plan export then timetable read uses the current URL, removes stale degree UI and exports only once", async () => {
  const state = setup(DEGREE_PLAN_URL, plan);
  state.button("campus-degree-import-host").click();
  expect(state.create).toHaveBeenCalledTimes(1);
  expect(state.sendMessage).not.toHaveBeenCalled();
  state.navigate(TIMETABLE, grid);
  await vi.waitFor(() => {
    expect(document.getElementById("campus-degree-import-host")).toBeNull();
    expect(document.getElementById("campus-schedule-import-host")).not.toBeNull();
  });
  await state.button("campus-schedule-import-host").click();
  await vi.waitFor(() => expect(state.sendMessage).toHaveBeenCalledTimes(1));
  expect(state.sendMessage.mock.calls[0][0]).toMatchObject({ type: "schedule-auto-observation", payload: {
    pathname: "/eams/courseTableForStd!courseTable.action", selectedTerm: "2026-2027学年1学期",
    rows: [["虚构课表甲(0001) (某甲)(1-17,示例楼101)", "星期一", "1-1"]],
  } });
  // The old toolbar listener must not download degree JSON from the timetable.
  const response = vi.fn();
  state.listeners.forEach(fn => fn({ type: "extract-visible-degree-plan" }, { id: "ext" }, response));
  expect(response).toHaveBeenCalledWith(expect.objectContaining({ ok: false }));
  expect(state.create).toHaveBeenCalledTimes(1);
});

it("timetable → degree → timetable toolbar reads current content without duplicate listeners or overlapping UI", async () => {
  const state = setup(TIMETABLE, grid);
  state.navigate(DEGREE_PLAN_URL, plan);
  await vi.waitFor(() => expect(document.getElementById("campus-degree-import-host")).not.toBeNull());
  expect(document.getElementById("campus-schedule-import-host")).toBeNull();
  const wrongResponse = vi.fn();
  state.listeners.forEach(fn => fn({ type: "extract-visible-schedule" }, { id: "ext" }, wrongResponse));
  expect(state.sendMessage).not.toHaveBeenCalled();
  expect(wrongResponse).toHaveBeenCalledWith(expect.objectContaining({ ok: false }));
  state.navigate(TIMETABLE, grid.replace("虚构课表甲", "虚构课表乙"));
  await vi.waitFor(() => expect(document.getElementById("campus-schedule-import-host")).not.toBeNull());
  const response = vi.fn();
  state.listeners.forEach(fn => fn({ type: "extract-visible-schedule" }, { id: "ext" }, response));
  expect(state.sendMessage).toHaveBeenCalledTimes(1);
  expect(state.sendMessage.mock.calls[0][0].payload.rows[0][0]).toContain("虚构课表乙");
  state.navigate(DEGREE_PLAN_URL, plan);
  await vi.waitFor(() => expect(document.getElementById("campus-degree-import-host")).not.toBeNull());
  expect(state.listeners).toHaveLength(2);
});

it("waits for the delayed timetable grid and removes both actions on other pages", async () => {
  const state = setup(TIMETABLE, "加载中");
  expect(document.getElementById("campus-schedule-import-host")).toBeNull();
  state.navigate(TIMETABLE, grid);
  await vi.waitFor(() => expect(document.getElementById("campus-schedule-import-host")).not.toBeNull());
  state.navigate("https://eamis.nankai.edu.cn/eams/grades.action", plan);
  await vi.waitFor(() => expect(document.getElementById("campus-schedule-import-host")).toBeNull());
  expect(document.getElementById("campus-degree-import-host")).toBeNull();
  expect(state.sendMessage).not.toHaveBeenCalled();
});
