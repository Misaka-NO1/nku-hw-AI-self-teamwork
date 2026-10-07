import { apiClient } from "../../shared/api/client";

export interface DemoSession {
  workspaceRef: string;
  csrfToken: string;
  expiresAt: string;
}
export interface Notice {
  title: string;
  event: { start: string | null; end: string | null; date: string | null; precision: string };
  due: { at: string | null; date: string | null; precision: string };
  estimatedMinutes: number | null;
  earliestStart: string | null;
  materials: string[];
  sourceSpans: { field: string; quote: string; sourceRef: string }[];
  needsConfirmation: string[];
}
export interface TaskDraft {
  draftId: string;
  kind: "task" | "schedule";
  workspaceRef: string;
  revision: number;
  payloadHash: string;
  status: "draft" | "committed";
  expiresAt: string;
  payload: Notice;
}
export interface TaskRecord {
  taskId: string;
  revision: number;
  notice: Notice;
  confirmedAt: string;
}
export interface SaveAttempt {
  draftId: string;
  revision: number;
  payloadHash: string;
  confirmationKey: string;
  commitKey: string;
  confirmationId?: string;
}
export interface TimeCheckResult {
  kind: "event_conflict" | "deadline_feasibility";
  conflicts?: { sourceEventId: string; intersectionStart: string; intersectionEnd: string }[];
  candidateSlots?: { start: string; end: string; durationMinutes: number }[];
  needsConfirmation: string[];
  coverage: { completeness?: string; scope?: string };
}

export const tasksApi = {
  createSession: () => apiClient.post<DemoSession>("/api/v1/demo/workspaces", { fixture_set_id: "demo-v1" }),
  list: (session: DemoSession) => apiClient.get<TaskRecord[]>(`/api/v1/tasks?${new URLSearchParams({ workspace_ref: session.workspaceRef })}`),
  draft: (draftId: string) => apiClient.get<TaskDraft>(`/api/v1/drafts/${encodeURIComponent(draftId)}`),
  checkTime: (query: unknown) => apiClient.post<TimeCheckResult>("/api/v1/time/check", query),
  async createDraft(session: DemoSession, notice: unknown, key: string) {
    const created = await apiClient.post<{ draftId: string }>("/api/v1/tasks/drafts", {
      workspace_ref: session.workspaceRef, notice,
    }, { headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": key } });
    return tasksApi.draft(created.draftId);
  },
};

/** Only invoked by the explicit confirmation button. Persist the same keys before
 * each request so a lost HTTP response or page refresh never creates a new write. */
export async function saveConfirmedDraft(
  session: DemoSession, draft: TaskDraft, attempt: SaveAttempt,
  persist: (attempt: SaveAttempt) => void,
): Promise<{ taskId: string; revision: number }> {
  if (draft.kind !== "task" || draft.workspaceRef !== session.workspaceRef || draft.payload.needsConfirmation.length) {
    throw new Error("草稿归属或待确认字段未通过，不能保存");
  }
  if (attempt.draftId !== draft.draftId || attempt.revision !== draft.revision || attempt.payloadHash !== draft.payloadHash) {
    throw new Error("草稿版本已改变，请重新查看后确认");
  }
  persist(attempt);
  if (!attempt.confirmationId) {
    const confirmed = await apiClient.post<{ confirmationId: string }>("/api/v1/confirmations", {
      draft_id: draft.draftId, revision: draft.revision, payload_hash: draft.payloadHash,
    }, { headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": attempt.confirmationKey } });
    attempt.confirmationId = confirmed.confirmationId;
    persist(attempt);
  }
  return apiClient.post("/api/v1/tasks/commit", {
    confirmation_id: attempt.confirmationId, idempotency_key: attempt.commitKey,
  }, { headers: { "X-CSRF-Token": session.csrfToken } });
}
