import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api/client";
import { DEMO_CACHE_KEY, readDemoSession, restoreBrowserSession, sessionExpired, rejectUnauthenticatedBrowserSession } from "../tasks/sessionCache";
import { saveConfirmedDraft, type TaskDraft, type SaveAttempt } from "../tasks/api";
import notice from "../../../../fixtures/notice-event.demo.json";
import { snakeToCamel } from "../../shared/api/convert";

const session = { workspaceRef: "pilot_workspace_A", csrfToken: "fictional-csrf-A", expiresAt: "2099-01-01T00:00:00+08:00" };
const checked = { workspace_ref: session.workspaceRef, csrf_token: session.csrfToken, expires_at: session.expiresAt,
  dataset_kind: "demo", personal_uploads: false, agent_paired: false };
const scheduleKey = "campus-demo-schedule-v1";
function response(data: unknown, status = 200, code = "AUTH_REQUIRED") {
  return new Response(JSON.stringify({ ok: status === 200, data: status === 200 ? data : null,
    error: status === 200 ? null : { code, message: "fixture request rejected" }, meta: { request_id: "request-session-read" } }), { status });
}
describe("Cookie-backed browser session recovery", () => {
  let storage: Map<string, string>;
  beforeEach(() => {
    storage = new Map();
    vi.stubEnv("VITE_API_BASE_URL", "/");
    vi.stubGlobal("sessionStorage", { getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) });
  });
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("recovers a new tab without local state using only the guarded GET", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(checked)); vi.stubGlobal("fetch", fetcher);
    expect(readDemoSession()).toBeNull();
    expect(await restoreBrowserSession()).toEqual(session);
    expect(readDemoSession()).toEqual(session);
    expect(fetcher).toHaveBeenCalledOnce();
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/api/v1/auth/cloudbase/browser-session");
    expect(options.method).toBe("GET"); expect(options.credentials).toBe("include");
    expect(options.headers).toEqual({ "X-Campus-Session-Read": "1" });
    expect(options.body).toBeUndefined();
  });
  it("preserves same-workspace retry keys without extending expiry", async () => {
    const cache = { session, draftKeys: { notice: "existing-draft-key" }, draftId: "draft_A",
      attempt: { confirmationId: "confirmation_A", commitKey: "existing-commit-key" } };
    storage.set(DEMO_CACHE_KEY, JSON.stringify(cache));
    storage.set(scheduleKey, JSON.stringify({ workspaceRef: session.workspaceRef, draftId: "schedule_A" }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(checked)));
    await restoreBrowserSession();
    expect(JSON.parse(storage.get(DEMO_CACHE_KEY)!)).toEqual(cache);
    expect(JSON.parse(storage.get(scheduleKey)!)).toHaveProperty("draftId", "schedule_A");
  });
  it("accepts the server-verified expiry when the client clock is ahead", async () => {
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2200-01-01T00:00:00Z"));
    const cache = { session, draftKeys: { notice: "existing-key" }, draftId: "draft_A" };
    storage.set(DEMO_CACHE_KEY, JSON.stringify(cache));
    expect(readDemoSession()).toBeNull(); // Local demo cache still uses the client clock.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(checked)));
    expect(await restoreBrowserSession()).toEqual(session);
    expect(JSON.parse(storage.get(DEMO_CACHE_KEY)!)).toEqual(cache);
  });
  it("keeps the valid browser session when a business confirmation expires", async () => {
    const draft = { draftId: "draft_A", workspaceRef: session.workspaceRef, kind: "task", revision: 1,
      payloadHash: "a".repeat(64), status: "draft", expiresAt: session.expiresAt,
      payload: snakeToCamel(notice) } as unknown as TaskDraft;
    const attempt: SaveAttempt = { draftId: draft.draftId, revision: draft.revision, payloadHash: draft.payloadHash,
      confirmationKey: "confirmation-key-existing", commitKey: "commit-key-existing", confirmationId: "confirmation-expired" };
    const cache = { session, draftKeys: { notice: "existing-key" }, draftId: draft.draftId, attempt };
    storage.set(DEMO_CACHE_KEY, JSON.stringify(cache));
    storage.set(scheduleKey, JSON.stringify({ workspaceRef: session.workspaceRef, draftId: "schedule_A" }));
    const fetcher = vi.fn().mockResolvedValue(response(null, 410, "TOKEN_EXPIRED")); vi.stubGlobal("fetch", fetcher);
    let error: unknown;
    try { await saveConfirmedDraft(session, draft, attempt, vi.fn()); } catch (value) { error = value; }
    expect(error).toMatchObject({ status: 410, code: "TOKEN_EXPIRED" });
    expect(rejectUnauthenticatedBrowserSession(error)).toBe(false);
    expect(readDemoSession()).toEqual(session);
    expect(JSON.parse(storage.get(DEMO_CACHE_KEY)!)).toEqual(cache);
    expect(storage.has(scheduleKey)).toBe(true);
    expect(fetcher).toHaveBeenCalledOnce(); expect(fetcher.mock.calls[0][0]).toBe("/api/v1/tasks/commit");
  });
  it("clears business state only when authentication itself is rejected", () => {
    storage.set(DEMO_CACHE_KEY, JSON.stringify({ session, draftKeys: {} })); storage.set(scheduleKey, "old");
    expect(rejectUnauthenticatedBrowserSession(new ApiError({ code: "AUTH_REQUIRED", status: 401,
      message: "Session rejected", requestId: "request-401" }))).toBe(true);
    expect(storage.size).toBe(0);
  });
  it("replaces stale account state with the Cookie owner and drops both old draft caches", async () => {
    storage.set(DEMO_CACHE_KEY, JSON.stringify({ session, draftKeys: { notice: "old-key" }, draftId: "draft_A", attempt: { commitKey: "old-commit" } }));
    storage.set(scheduleKey, JSON.stringify({ workspaceRef: session.workspaceRef, draftId: "schedule_A" }));
    const other = { ...checked, workspace_ref: "pilot_workspace_B", csrf_token: "fictional-csrf-B" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(other)));
    const restored = await restoreBrowserSession();
    expect(restored.workspaceRef).toBe("pilot_workspace_B");
    expect(JSON.parse(storage.get(DEMO_CACHE_KEY)!)).toEqual({ session: restored, draftKeys: {} });
    expect(storage.has(scheduleKey)).toBe(false);
  });
  it.each([401, 410])("requires login and clears local state after HTTP %s", async status => {
    storage.set(DEMO_CACHE_KEY, JSON.stringify({ session, draftKeys: {} })); storage.set(scheduleKey, "old");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(null, status, status === 410 ? "TOKEN_EXPIRED" : "AUTH_REQUIRED")));
    let error: unknown; try { await restoreBrowserSession(); } catch (value) { error = value; }
    expect(error).toBeInstanceOf(ApiError); expect(sessionExpired(error)).toBe(true);
    expect(storage.size).toBe(0);
  });
  it("surfaces dependency failure without using cached identity or calling anonymous login", async () => {
    storage.set(DEMO_CACHE_KEY, JSON.stringify({ session, draftKeys: {} }));
    const fetcher = vi.fn().mockResolvedValue(response(null, 503, "DEPENDENCY_UNAVAILABLE")); vi.stubGlobal("fetch", fetcher);
    await expect(restoreBrowserSession()).rejects.toMatchObject({ status: 503, requestId: "request-session-read" });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(sessionExpired(new ApiError({ code: "DEPENDENCY_UNAVAILABLE", status: 503, message: "unavailable", requestId: null }))).toBe(false);
  });
  it.each([{ ...checked, dataset_kind: "personal" }, { ...checked, personal_uploads: true },
    { ...checked, agent_paired: true }, { ...checked, expires_at: "not-a-date" },
    { ...checked, csrf_token: "" }, null])("rejects invalid recovery metadata", async data => {
      storage.set(DEMO_CACHE_KEY, JSON.stringify({ session, draftKeys: {} }));
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(data)));
      await expect(restoreBrowserSession()).rejects.toThrow("会话恢复状态不一致");
      expect(readDemoSession()).toBeNull();
    });
});
