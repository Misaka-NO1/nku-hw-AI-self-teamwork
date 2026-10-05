import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveConfirmedSchedule, scheduleApi, type ScheduleDraft } from "./connectedApi";
import type { SaveAttempt } from "../tasks/api";
import fixture from "../../../../fixtures/timetable.demo.json";

const session = { workspaceRef: "owned-workspace", csrfToken: "fictional-csrf", expiresAt: "2099-01-01T00:00:00+08:00" };
const draft: ScheduleDraft = { draftId: "schedule-draft-1", kind: "schedule", workspaceRef: session.workspaceRef,
  revision: 1, payloadHash: "a".repeat(64), status: "draft", expiresAt: session.expiresAt, payload: fixture as ScheduleDraft["payload"] };
const attempt = (): SaveAttempt => ({ draftId: draft.draftId, revision: 1, payloadHash: draft.payloadHash,
  confirmationKey: "confirm-schedule-1", commitKey: "commit-schedule-1" });
const success = (data: unknown) => new Response(JSON.stringify({ ok: true, data, error: null, meta: { request_id: "test-request" } }));
describe("已连接的课表确认与读回", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "/"));
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("draft/current 只读恢复 B 的原契约字段，不产生确认或提交", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(success({ ...draft, payload: fixture }))
      .mockResolvedValueOnce(success({ schedule_id: "saved-1", revision: 1, timetable: fixture }));
    vi.stubGlobal("fetch", fetcher);
    expect((await scheduleApi.draft(draft.draftId)).payload).toEqual(fixture);
    expect((await scheduleApi.current(session)).timetable).toEqual(fixture);
    expect(fetcher.mock.calls.every(call => call[1].method === "GET")).toBe(true);
  });
  it("明确确认才写，提交响应丢失可用同一回执和幂等键重试", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(success({ confirmation_id: "receipt-1" }))
      .mockRejectedValueOnce(new Error("connection lost"))
      .mockResolvedValueOnce(success({ schedule_id: "saved-1", revision: 1 }));
    vi.stubGlobal("fetch", fetcher);
    const pending = attempt(); const persist = vi.fn();
    await expect(saveConfirmedSchedule(session, draft, pending, persist)).rejects.toThrow();
    expect(pending.confirmationId).toBe("receipt-1");
    expect(await saveConfirmedSchedule(session, draft, pending, persist)).toEqual({ scheduleId: "saved-1", revision: 1 });
    expect(fetcher.mock.calls.filter(call => call[0] === "/api/v1/confirmations")).toHaveLength(1);
    expect(fetcher.mock.calls[1][1].body).toBe(fetcher.mock.calls[2][1].body);
    expect(fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe(session.csrfToken);
  });
  it.each(["owner", "revision", "expired", "invalid_expiry", "kind"])("%s 不发任何写请求", async kind => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const invalid = { ...draft };
    if (kind === "owner") invalid.workspaceRef = "another-account";
    if (kind === "revision") invalid.revision = 2;
    if (kind === "expired") invalid.expiresAt = "2000-01-01T00:00:00+08:00";
    if (kind === "invalid_expiry") invalid.expiresAt = "not-a-date";
    if (kind === "kind") (invalid as { kind: string }).kind = "task";
    await expect(saveConfirmedSchedule(session, invalid, attempt(), vi.fn())).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
});
