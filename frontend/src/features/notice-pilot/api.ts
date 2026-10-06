import { apiClient } from "../../shared/api/client";

export type TimeWindow = { start: string; end: string };
export type Slot = TimeWindow & { durationMinutes: number };
export type Kind = "event_conflict" | "deadline_feasibility";
export interface Notice {
  schemaVersion: string;
  noticeId: string;
  title: string;
  publishedAt: string | null;
  extractedAt: string;
  timezone: string;
  event: { start: string | null; end: string | null; date: string | null; precision: string };
  due: { at: string | null; date: string | null; precision: string };
  estimatedMinutes: number | null;
  earliestStart: string | null;
  materials: string[];
  sourceSpans: { field: string; quote: string; sourceRef: string }[];
  needsConfirmation: string[];
}
export interface Confirmations {
  sourceReview: boolean;
  acceptConflicts: boolean;
  estimatedMinutes: number | null;
  earliestStart: string | null;
  dueAt: string | null;
  eventStart: string | null;
  eventEnd: string | null;
}
export interface ReadRequest { sourceText: string; sourceRef: string; referenceAt: string | null }
export interface CheckRequest extends ReadRequest {
  itemId: string;
  window: TimeWindow;
  availableWindows: TimeWindow[];
  userConfirmations: Confirmations;
}
export interface Plan extends ReadRequest {
  planVersion: string;
  notice: Notice;
  kind: Kind;
  window: TimeWindow;
  availableWindows: TimeWindow[];
  userConfirmations: Confirmations;
  selectedSlot: Slot | null;
}
export interface Batch {
  items: { kind: Kind; notice: Notice }[];
  unclassified: { quote: string; sourceRef: string }[];
  coverage: { charactersRead: number; charactersTotal: number };
  limitations: string[];
}
export interface CheckResult {
  plan: Plan;
  timeRequest: unknown;
  timeResult: {
    kind: Kind;
    candidateSlots?: Slot[];
    conflicts?: { sourceEventId: string; intersectionStart: string; intersectionEnd: string }[];
    needsConfirmation: string[];
    coverage: { withinTerm: boolean };
  };
  recommendations: { slot: Slot; reason: string; candidateIndex: number }[];
  conflictLabels: Record<string, string>;
  coverageMessage: string;
}
export interface Session { workspaceRef: string; csrfToken: string; expiresAt: string }
export interface Draft {
  draftId: string; kind: "task" | "schedule"; revision: number; payloadHash: string;
  status: string; payload?: Plan;
}
export interface Task { taskId: string; notice: Plan | Notice; confirmedAt: string }

/** Convert the shared client's camelCase view back at the request boundary. */
export function toWire(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(toWire);
  if (value && typeof value === "object") return Object.fromEntries(
    Object.entries(value).map(([key, val]) => [key.replace(/[A-Z]/g, c => `_${c.toLowerCase()}`), toWire(val)]),
  );
  return value;
}

export const noticeApi = {
  createSession: () => apiClient.post<Session>("/api/v1/notice-pilot/workspaces", { fictional_data_confirmed: true }),
  read: (body: ReadRequest, csrf: string) => apiClient.post<Batch>("/api/v1/notice-pilot/read", toWire(body),
    { headers: { "X-CSRF-Token": csrf } }),
  check: (body: CheckRequest, csrf: string) => apiClient.post<CheckResult>("/api/v1/notice-pilot/check", toWire(body),
    { headers: { "X-CSRF-Token": csrf } }),
  draft: (plan: Plan, csrf: string, key: string) => apiClient.post<Draft>("/api/v1/notice-pilot/drafts", { plan: toWire(plan) },
    { headers: { "X-CSRF-Token": csrf, "Idempotency-Key": key } }),
  update: (draft: Draft, plan: Plan, csrf: string) => apiClient.post<Draft>(`/api/v1/notice-pilot/drafts/${encodeURIComponent(draft.draftId)}/update`,
    { revision: draft.revision, plan: toWire(plan) }, { headers: { "X-CSRF-Token": csrf } }),
  getDraft: (id: string) => apiClient.get<Draft>(`/api/v1/drafts/${encodeURIComponent(id)}`),
  list: (ref: string) => apiClient.get<Task[]>(`/api/v1/tasks?${new URLSearchParams({ workspace_ref: ref })}`),
  scheduleDraft: (timetable: unknown, csrf: string, key: string) => apiClient.post<Draft>("/api/v1/schedules/import-drafts", timetable,
    { headers: { "X-CSRF-Token": csrf, "Idempotency-Key": key } }),
  confirm: (draft: Draft, csrf: string, key: string) => apiClient.post<{ confirmationId: string }>("/api/v1/confirmations",
    { draft_id: draft.draftId, revision: draft.revision, payload_hash: draft.payloadHash },
    { headers: { "X-CSRF-Token": csrf, "Idempotency-Key": key } }),
  commit: (kind: "schedule" | "task", ticket: string, csrf: string, key: string) =>
    apiClient.post<{ taskId?: string; scheduleId?: string }>(`/api/v1/${kind === "task" ? "tasks" : "schedules"}/commit`,
      { confirmation_id: ticket, idempotency_key: key }, { headers: { "X-CSRF-Token": csrf } }),
};
