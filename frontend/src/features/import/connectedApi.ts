import type { TimetableImport } from "@campus/import-core";
import { apiClient } from "../../shared/api/client";
import { camelToSnake } from "../../shared/api/convert";
import { tasksApi, type DemoSession, type SaveAttempt } from "../tasks/api";

export interface ScheduleDraft {
  draftId: string; kind: "schedule"; workspaceRef: string; revision: number;
  payloadHash: string; status: "draft" | "committed"; expiresAt: string;
  payload: TimetableImport;
}
export interface CurrentSchedule {
  scheduleId: string; workspaceRef: string; revision: number;
  timetable: TimetableImport; confirmedAt: string;
}
export const scheduleApi = {
  async draft(id: string): Promise<ScheduleDraft> {
    const item = await apiClient.get<ScheduleDraft>(`/api/v1/drafts/${encodeURIComponent(id)}`);
    return { ...item, payload: camelToSnake(item.payload) };
  },
  async createDraft(session: DemoSession, payload: TimetableImport, key: string) {
    const item = await apiClient.post<{ draftId: string }>("/api/v1/schedules/import-drafts", payload,
      { headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": key } });
    return scheduleApi.draft(item.draftId);
  },
  async current(session: DemoSession): Promise<CurrentSchedule> {
    const item = await apiClient.get<CurrentSchedule>(`/api/v1/schedules/current?${new URLSearchParams({ workspace_ref: session.workspaceRef })}`);
    return { ...item, timetable: camelToSnake(item.timetable) };
  },
  validate: (payload: TimetableImport) => apiClient.post<{ valid: boolean; issues: unknown[] }>("/api/v1/schedules/validate", payload),
  createSession: tasksApi.createSession,
};

/** Called only from the visible human confirmation button. Never on mount. */
export async function saveConfirmedSchedule(session: DemoSession, draft: ScheduleDraft,
  attempt: SaveAttempt, persist: (item: SaveAttempt) => void): Promise<{ scheduleId: string; revision: number }> {
  if (draft.kind !== "schedule" || draft.workspaceRef !== session.workspaceRef
    || draft.draftId !== attempt.draftId || draft.revision !== attempt.revision
    || draft.payloadHash !== attempt.payloadHash || !Number.isFinite(Date.parse(draft.expiresAt))
    || Date.parse(draft.expiresAt) <= Date.now()) {
    throw new Error("课表草稿归属、版本或有效期已变化，请重新核对");
  }
  persist(attempt);
  if (!attempt.confirmationId) {
    const receipt = await apiClient.post<{ confirmationId: string }>("/api/v1/confirmations", {
      draft_id: draft.draftId, revision: draft.revision, payload_hash: draft.payloadHash,
    }, { headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": attempt.confirmationKey } });
    attempt.confirmationId = receipt.confirmationId;
    persist(attempt);
  }
  return apiClient.post("/api/v1/schedules/commit", {
    confirmation_id: attempt.confirmationId, idempotency_key: attempt.commitKey,
  }, { headers: { "X-CSRF-Token": session.csrfToken } });
}
