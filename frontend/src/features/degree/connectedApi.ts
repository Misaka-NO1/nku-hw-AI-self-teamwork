import { apiClient, ApiError } from "../../shared/api/client";
import { camelToSnake } from "../../shared/api/convert";
import type { DemoSession, SaveAttempt } from "../tasks/api";
import type { PageReport } from "./pageApi";

export interface DegreeDraft {
  draftId: string; kind: "degree"; workspaceRef: string; revision: number;
  payloadHash: string; status: "draft" | "committed"; expiresAt: string;
  payload: unknown; report: PageReport;
}
export interface CurrentDegree {
  degreeId: string; workspaceRef: string; revision: number; confirmedAt: string;
  observation: unknown; report: PageReport;
}
export const degreeApi = {
  async draft(id: string, signal?: AbortSignal): Promise<DegreeDraft> {
    const item = await apiClient.get<DegreeDraft>(`/api/v1/degree/drafts/${encodeURIComponent(id)}`, { signal });
    return { ...item, payload: camelToSnake(item.payload) };
  },
  async createDraft(session: DemoSession, observation: unknown, key: string, signal?: AbortSignal) {
    const item = await apiClient.post<{ draftId: string }>("/api/v1/degree/import-drafts", observation,
      { signal, headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": key } });
    if (signal?.aborted) throw new Error("登录会话已变化，请重新核对");
    return degreeApi.draft(item.draftId, signal);
  },
  async current(signal?: AbortSignal): Promise<CurrentDegree> {
    const item = await apiClient.get<CurrentDegree | null>("/api/v1/degree/current", { signal });
    if (!item) throw new ApiError({ code: "NOT_FOUND", message: "尚未保存本人培养计划", status: 404, requestId: null });
    return { ...item, observation: camelToSnake(item.observation) };
  },
};

/** Only called by the human's explicit confirm/save button, as for timetable. */
export async function saveConfirmedDegree(session: DemoSession, draft: DegreeDraft,
  attempt: SaveAttempt, persist: (item: SaveAttempt) => void, guard: () => void, signal?: AbortSignal) {
  guard();
  if (draft.kind !== "degree" || draft.workspaceRef !== session.workspaceRef
    || draft.draftId !== attempt.draftId || draft.revision !== attempt.revision
    || draft.payloadHash !== attempt.payloadHash || !Number.isFinite(Date.parse(draft.expiresAt))
    || Date.parse(draft.expiresAt) <= Date.now()) throw new Error("培养计划草稿归属、版本或有效期已变化，请重新核对");
  persist(attempt);
  if (!attempt.confirmationId) {
    const receipt = await apiClient.post<{ confirmationId: string }>("/api/v1/degree/confirmations", {
      draft_id: draft.draftId, revision: draft.revision, payload_hash: draft.payloadHash, share_with_agent: true,
    }, { signal, headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": attempt.confirmationKey } });
    attempt.confirmationId = receipt.confirmationId;
    persist(attempt);
  }
  guard();
  return apiClient.post<{ degreeId: string; revision: number }>("/api/v1/degree/commit", {
    confirmation_id: attempt.confirmationId, idempotency_key: attempt.commitKey,
  }, { signal, headers: { "X-CSRF-Token": session.csrfToken } });
}
