import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../shared/api/client";
import { degreeApi, saveConfirmedDegree, type DegreeDraft } from "./connectedApi";
import type { PageReport } from "./pageApi";
import type { SaveAttempt } from "../tasks/api";
vi.mock("../../shared/api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));
const session = { workspaceRef: "owner-a", csrfToken: "csrf-a", expiresAt: "2099-01-01", datasetKind: "personal" as const };
const draft: DegreeDraft = { draftId: "draft-test", kind: "degree", workspaceRef: "owner-a", revision: 1,
  payloadHash: "hash-a", status: "draft", expiresAt: "2099-01-01", payload: {}, report: {} as PageReport };
const attempt = (): SaveAttempt => ({ draftId: draft.draftId, revision: 1, payloadHash: draft.payloadHash,
  confirmationKey: "confirm-key-a", commitKey: "commit-key-a" });
describe("本人培养计划沿用课表确认保存协议", () => {
  beforeEach(() => vi.resetAllMocks());
  it("明确确认后才发确认与保存，重试沿用回执与幂等键", async () => {
    const value = attempt(), persist = vi.fn(), guard = vi.fn();
    vi.mocked(apiClient.post).mockResolvedValueOnce({ confirmationId: "receipt-a" }).mockResolvedValue({ degreeId: "degree-a", revision: 1 });
    await saveConfirmedDegree(session, draft, value, persist, guard);
    expect(apiClient.post).toHaveBeenNthCalledWith(1, "/api/v1/degree/confirmations", {
      draft_id: draft.draftId, revision: 1, payload_hash: draft.payloadHash, share_with_agent: true,
    }, { signal: undefined, headers: { "X-CSRF-Token": "csrf-a", "Idempotency-Key": "confirm-key-a" } });
    expect(apiClient.post).toHaveBeenNthCalledWith(2, "/api/v1/degree/commit", {
      confirmation_id: "receipt-a", idempotency_key: "commit-key-a",
    }, { signal: undefined, headers: { "X-CSRF-Token": "csrf-a" } });
    await saveConfirmedDegree(session, draft, value, persist, guard);
    expect(apiClient.post).toHaveBeenCalledTimes(3);
    expect(value.confirmationId).toBe("receipt-a");
  });
  it("归属不符或草稿过期不请求确认或保存", async () => {
    await expect(saveConfirmedDegree(session, { ...draft, workspaceRef: "owner-b" }, attempt(), vi.fn(), vi.fn())).rejects.toThrow("归属");
    await expect(saveConfirmedDegree(session, { ...draft, expiresAt: "2000-01-01" }, attempt(), vi.fn(), vi.fn())).rejects.toThrow("有效期");
    expect(apiClient.post).not.toHaveBeenCalled();
  });
  it("确认请求后账号重新核验，停止自动保存", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ confirmationId: "receipt-a" });
    const guard = vi.fn().mockImplementationOnce(() => {}).mockImplementationOnce(() => { throw new Error("owner changed"); });
    await expect(saveConfirmedDegree(session, draft, attempt(), vi.fn(), guard)).rejects.toThrow("owner changed");
    expect(apiClient.post).toHaveBeenCalledTimes(1);
  });
  it("读回及导入不传 owner，保留空格和原布尔值", async () => {
    const observation = { kind: "degree-table-observation", source: { adapter_verified: false }, rows: [{ cells: ["", "2"] }] };
    vi.mocked(apiClient.post).mockResolvedValue({ draftId: "draft-test" });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ ...draft, payload: { source: { adapterVerified: false }, rows: [{ cells: ["", "2"] }] } });
    const item = await degreeApi.createDraft(session, observation, "draft-key-a");
    expect(item.payload).toEqual({ source: { adapter_verified: false }, rows: [{ cells: ["", "2"] }] });
    expect(vi.mocked(apiClient.post).mock.calls[0][1]).toEqual(observation);
    vi.mocked(apiClient.get).mockResolvedValueOnce({ observation: { source: { adapterVerified: false } } });
    await degreeApi.current();
    expect(apiClient.get).toHaveBeenLastCalledWith("/api/v1/degree/current", { signal: undefined });
  });
});
