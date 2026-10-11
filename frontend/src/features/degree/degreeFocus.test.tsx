// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { DegreeReadPreview } from "./DegreeReadPreview";
import { restoreBrowserSession } from "../tasks/sessionCache";
import { degreeApi } from "./connectedApi";
import { ApiError } from "../../shared/api/client";
vi.mock("../tasks/sessionCache", () => ({ restoreBrowserSession: vi.fn(), readDemoSession: vi.fn(),
  sessionExpired: vi.fn(), rejectUnauthenticatedBrowserSession: vi.fn() }));
vi.mock("./connectedApi", () => ({ degreeApi: { current: vi.fn(), createDraft: vi.fn() }, saveConfirmedDegree: vi.fn() }));
const owner = { workspaceRef: "fictional-focus-owner", csrfToken: "fictional", expiresAt: "2099-01-01T00:00:00Z" };
const observation = { kind: "degree-table-observation", source: {
  url: "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", captured_at: "2026-10-10T00:00:00Z",
  coverage: "unknown", adapter_verified: false }, headers: ["课程名称"],
  rows: [{ locator: "table-row:2", cells: ["虚构一次性转交课程"] }] };

it("real session focus recheck hides the receipt, then retains it only for the same verified owner", async () => {
  vi.mocked(degreeApi.current).mockRejectedValue(new ApiError({ code: "NOT_FOUND", message: "empty", status: 404, requestId: "test" }));
  vi.stubEnv("VITE_IDENTITY_PILOT", "true"); vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  let complete!: (session: typeof owner) => void;
  vi.mocked(restoreBrowserSession).mockResolvedValueOnce(owner)
    .mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
  try {
    await act(async () => root.render(<DegreeReadPreview />));
    await act(async () => window.dispatchEvent(new CustomEvent("campus:degree-observation", { detail: observation })));
    expect(host.textContent).toContain("虚构一次性转交课程");
    await act(async () => window.dispatchEvent(new Event("focus")));
    expect(host.textContent).not.toContain("虚构一次性转交课程");
    await act(async () => complete({ ...owner, csrfToken: "fictional-refreshed" }));
    expect(host.textContent).toContain("虚构一次性转交课程");
    expect(degreeApi.createDraft).not.toHaveBeenCalled();
    vi.mocked(restoreBrowserSession).mockResolvedValueOnce({ ...owner, workspaceRef: "fictional-other-owner" });
    await act(async () => window.dispatchEvent(new Event("focus")));
    expect(host.textContent).not.toContain("虚构一次性转交课程");
    expect(host.textContent).toContain("尚未收到");
  } finally {
    await act(async () => root.unmount()); host.remove(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetAllMocks();
  }
});

it("does not claim a one-shot extension receipt until the browser identity is verified", async () => {
  vi.mocked(degreeApi.current).mockRejectedValue(new ApiError({ code: "NOT_FOUND", message: "empty", status: 404, requestId: "test" }));
  vi.stubEnv("VITE_IDENTITY_PILOT", "true"); vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  let complete!: (session: typeof owner) => void;
  vi.mocked(restoreBrowserSession).mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  const ready = vi.fn(); window.addEventListener("campus:degree-import-ready", ready);
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
  try {
    await act(async () => root.render(<DegreeReadPreview />));
    expect(ready).not.toHaveBeenCalled();
    await act(async () => window.dispatchEvent(new Event("campus:degree-bridge-ready")));
    expect(ready).not.toHaveBeenCalled();
    await act(async () => complete(owner));
    expect(ready).toHaveBeenCalled();
  } finally {
    await act(async () => root.unmount()); host.remove(); window.removeEventListener("campus:degree-import-ready", ready);
    vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetAllMocks();
  }
});
