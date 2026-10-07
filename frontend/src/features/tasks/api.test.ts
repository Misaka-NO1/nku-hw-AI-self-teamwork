import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { saveConfirmedDraft, tasksApi, type TaskDraft, type SaveAttempt } from "./api";
import notice from "../../../../fixtures/notice-event.demo.json";
import { snakeToCamel } from "../../shared/api/convert";

const session = { workspaceRef: "demo-workspace-owned", csrfToken: "fictional-csrf", expiresAt: "2099-01-01T00:00:00+08:00" };
const draft = { draftId: "task-draft-1", workspaceRef: session.workspaceRef, kind: "task", revision: 1, payloadHash: "a".repeat(64), status: "draft", payload: snakeToCamel(notice) } as unknown as TaskDraft;
const attempt = (): SaveAttempt => ({ draftId: draft.draftId, revision: 1, payloadHash: draft.payloadHash, confirmationKey: "confirm-key-1", commitKey: "commit-key-1" });
function success(data: unknown) {
  return new Response(JSON.stringify({ ok: true, data, error: null, meta: { request_id: "request-test" } }), { status: 200 });
}
describe("待办确认与幂等传输", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "/"));
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("确认后才提交，snake_case 与 CSRF/幂等键正确", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(success({ confirmation_id: "confirmation-1" })).mockResolvedValueOnce(success({ task_id: "task-1", revision: 1 }));
    vi.stubGlobal("fetch", fetcher);
    const persist = vi.fn();
    expect(await saveConfirmedDraft(session, draft, attempt(), persist)).toEqual({ taskId: "task-1", revision: 1 });
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/confirmations");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ draft_id: "task-draft-1", revision: 1, payload_hash: draft.payloadHash });
    expect(fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe(session.csrfToken);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ confirmation_id: "confirmation-1", idempotency_key: "commit-key-1" });
    expect(persist).toHaveBeenCalledTimes(2);
  });
  it("提交响应丢失后复用回执和相同幂等键，不二次确认", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(success({ confirmation_id: "confirmation-1" })).mockRejectedValueOnce(new TypeError("network lost")).mockResolvedValueOnce(success({ task_id: "task-1", revision: 1 }));
    vi.stubGlobal("fetch", fetcher);
    const pending = attempt();
    await expect(saveConfirmedDraft(session, draft, pending, vi.fn())).rejects.toThrow();
    expect(pending.confirmationId).toBe("confirmation-1");
    await expect(saveConfirmedDraft(session, draft, pending, vi.fn())).resolves.toHaveProperty("taskId", "task-1");
    expect(fetcher.mock.calls[1][1].body).toBe(fetcher.mock.calls[2][1].body);
    expect(fetcher.mock.calls.filter(([url]) => url === "/api/v1/confirmations")).toHaveLength(1);
  });
  it("确认响应丢失后用原确认键重试", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new TypeError("network lost")).mockResolvedValueOnce(success({ confirmation_id: "confirmation-1" })).mockResolvedValueOnce(success({ task_id: "task-1", revision: 1 }));
    vi.stubGlobal("fetch", fetcher);
    const pending = attempt();
    await expect(saveConfirmedDraft(session, draft, pending, vi.fn())).rejects.toThrow();
    await saveConfirmedDraft(session, draft, pending, vi.fn());
    expect(fetcher.mock.calls[0][1].headers["Idempotency-Key"]).toBe(fetcher.mock.calls[1][1].headers["Idempotency-Key"]);
  });
  it.each(["ambiguous", "owner", "revision"])("%s 草稿被拒绝，完全不发送写请求", async (caseName) => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const invalid = { ...draft, payload: { ...draft.payload } };
    if (caseName === "ambiguous") invalid.payload.needsConfirmation = ["due_time"];
    if (caseName === "owner") invalid.workspaceRef = "someone-else";
    if (caseName === "revision") invalid.revision = 2;
    await expect(saveConfirmedDraft(session, invalid, attempt(), vi.fn())).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("创建只读回真实草稿，不自动确认或提交", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(success({ draft_id: "task-draft-1" })).mockResolvedValueOnce(success({ draft_id: "task-draft-1", payload: notice }));
    vi.stubGlobal("fetch", fetcher);
    const result = await tasksApi.createDraft(session, notice, "draft-key-001");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ workspace_ref: session.workspaceRef, notice });
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/drafts/task-draft-1");
    expect(result.payload.event.start).toBe(notice.event.start);
    expect(fetcher.mock.calls).toHaveLength(2);
  });
});
